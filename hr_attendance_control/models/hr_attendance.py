from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    violation_ids = fields.One2many(
        'hr.attendance.violation', 'attendance_id',
        string='Vi phạm phát sinh'
    )
    has_violation = fields.Boolean(
        compute='_compute_has_violation', store=True
    )

    @api.depends('violation_ids')
    def _compute_has_violation(self):
        for rec in self:
            rec.has_violation = bool(rec.violation_ids)

    def write(self, vals):
        """
        Override write() để detect vi phạm ngay khi check_out được ghi.
        Chỉ chạy detection khi có check_out và chưa có vi phạm nào.
        """
        result = super().write(vals)
        if 'check_out' in vals:
            for rec in self:
                # Tránh detect lại nếu đã có violation từ lần write trước
                if rec.check_out and not rec.violation_ids:
                    try:
                        rec._detect_and_create_violations()
                    except Exception as e:
                        _logger.error(
                            'Attendance violation detection failed for %s: %s',
                            rec.employee_id.name, str(e)
                        )
        return result

    def _detect_and_create_violations(self):
        """
        Logic chính: so sánh attendance thực tế với work schedule.
        Tạo violation record cho từng rule bị kích hoạt.
        """
        self.ensure_one()
        employee = self.employee_id
        schedule = employee.resource_calendar_id
        if not schedule:
            return

        # Lấy giờ làm dự kiến theo lịch làm việc
        attendance_date = self.check_in.date()
        planned = self._get_planned_attendance(schedule, attendance_date)
        if not planned:
            # Ngày này không phải ngày làm việc theo lịch
            return

        planned_start, planned_end = planned
        check_in_local = self._to_local_time(self.check_in)
        check_out_local = self._to_local_time(self.check_out)

        # Lấy tất cả rules đang active và áp dụng cho nhân viên này
        active_rules = self.env['hr.attendance.rule'].search([
            ('is_active', '=', True),
            ('violation_type', 'in', ['late', 'early_leave', 'insufficient_hours']),
        ])
        applicable_rules = active_rules.filtered(
            lambda r: r.applies_to_employee(employee)
        )

        violations_created = []

        for rule in applicable_rules:
            violation_data = None

            if rule.violation_type == 'late':
                # Tính phút đi muộn (trừ grace period)
                late_seconds = (check_in_local - planned_start).total_seconds()
                late_minutes = max(0, late_seconds / 60 - rule.grace_period_minutes)

                if late_minutes >= rule.threshold_minutes:
                    # Kiểm tra có nằm trong khoảng max của rule này không
                    if not rule.threshold_minutes_max or \
                            late_minutes < rule.threshold_minutes_max:
                        violation_data = {
                            'violation_type': 'late',
                            'deviation_minutes': late_minutes,
                        }

            elif rule.violation_type == 'early_leave':
                # Tính phút về sớm
                early_seconds = (planned_end - check_out_local).total_seconds()
                early_minutes = max(0, early_seconds / 60)

                if early_minutes >= rule.threshold_minutes:
                    if not rule.threshold_minutes_max or \
                            early_minutes < rule.threshold_minutes_max:
                        violation_data = {
                            'violation_type': 'early_leave',
                            'deviation_minutes': early_minutes,
                        }

            elif rule.violation_type == 'insufficient_hours':
                planned_hours = (planned_end - planned_start).total_seconds() / 3600
                actual_hours = self.worked_hours
                shortage = planned_hours - actual_hours

                if shortage * 60 >= rule.threshold_minutes:
                    violation_data = {
                        'violation_type': 'insufficient_hours',
                        'deviation_minutes': shortage * 60,
                    }

            if violation_data:
                penalty = self._calculate_penalty(rule, employee, violation_data)
                violation = self.env['hr.attendance.violation'].create({
                    'attendance_id': self.id,
                    'employee_id': employee.id,
                    'rule_id': rule.id,
                    'date': attendance_date,
                    'violation_type': violation_data['violation_type'],
                    'severity': rule.severity,
                    'deviation_minutes': violation_data['deviation_minutes'],
                    'penalty_points': rule.penalty_points,
                    'penalty_amount': penalty,
                    'state': 'detected',
                })
                violations_created.append(violation)

        # Gửi thông báo nếu có vi phạm
        if violations_created:
            self._notify_violations(violations_created)

    def _get_planned_attendance(self, schedule, work_date):
        """
        Tra cứu giờ làm dự kiến từ resource.calendar.
        Trả về (planned_start_datetime, planned_end_datetime) hoặc None.
        """
        # Lấy day_of_week: Monday=0 ... Sunday=6
        weekday = work_date.weekday()

        # Tìm attendance line trong resource.calendar cho ngày này
        attendance_lines = schedule.attendance_ids.filtered(
            lambda a: int(a.dayofweek) == weekday
        )
        if not attendance_lines:
            return None  # Không phải ngày làm việc

        # Lấy giờ sớm nhất và muộn nhất (support nhiều shift trong ngày)
        from datetime import datetime, time as dt_time
        import pytz

        tz = pytz.timezone(self.employee_id.tz or 'Asia/Ho_Chi_Minh')

        min_hour = min(float(a.hour_from) for a in attendance_lines)
        max_hour = max(float(a.hour_to) for a in attendance_lines)

        def hour_to_dt(hour_float):
            h = int(hour_float)
            m = int((hour_float - h) * 60)
            local_dt = tz.localize(datetime.combine(work_date, dt_time(h, m)))
            return local_dt

        return hour_to_dt(min_hour), hour_to_dt(max_hour)

    def _calculate_penalty(self, rule, employee, violation_data):
        """
        Tính tiền phạt dựa trên rule và thông tin lương nhân viên.
        """
        contract = employee.contract_id
        if not contract:
            return 0.0

        monthly_wage = contract.wage
        # Lương ngày = lương tháng / 26 công
        daily_wage = monthly_wage / 26
        hourly_wage = daily_wage / 8

        if rule.penalty_type == 'fixed':
            return rule.penalty_value

        elif rule.penalty_type == 'percent_daily':
            return daily_wage * rule.penalty_value / 100

        elif rule.penalty_type == 'percent_hourly':
            shortage_hours = violation_data.get('deviation_minutes', 0) / 60
            return hourly_wage * shortage_hours * rule.penalty_value / 100

        return 0.0

    def _notify_violations(self, violations):
        """Gửi thông báo tổng hợp đến nhân viên và manager qua Discuss"""
        employee = self.employee_id
        manager = employee.parent_id

        violation_summary = '\n'.join([
            f'• {v.get_violation_type_label()}: {v.deviation_minutes:.0f} phút — '
            f'Phạt: {v.penalty_amount:,.0f} VNĐ'
            for v in violations
        ])

        body = (
            f'<p>Phát hiện vi phạm chấm công ngày '
            f'<b>{violations[0].date}</b>:</p>'
            f'<pre>{violation_summary}</pre>'
            f'<p>Vui lòng giải trình trong vòng 48 giờ nếu có lý do hợp lệ.</p>'
        )

        # Gửi cho nhân viên
        if employee.user_id:
            self.env['mail.message'].create({
                'body': body,
                'res_id': violations[0].id,
                'res_model': 'hr.attendance.violation',
                'message_type': 'comment',
                'partner_ids': [(4, employee.user_id.partner_id.id)],
            })

        # Gửi cho manager
        if manager and manager.user_id:
            self.env['mail.message'].create({
                'body': f'<p>Nhân viên <b>{employee.name}</b> có vi phạm chấm công. '
                        f'Vui lòng xem xét và phê duyệt/từ chối giải trình.</p>' + body,
                'res_id': violations[0].id,
                'res_model': 'hr.attendance.violation',
                'message_type': 'comment',
                'partner_ids': [(4, manager.user_id.partner_id.id)],
            })

        # Tạo mail.activity nhắc giải trình cho nhân viên
        if violations[0].rule_id.requires_explanation and employee.user_id:
            violations[0].activity_schedule(
                'hr_attendance_control.activity_violation_explanation',
                note=f'Giải trình vi phạm chấm công ngày {violations[0].date}',
                user_id=employee.user_id.id,
                deadline=fields.Date.today() + timedelta(days=2),
            )

    def _to_local_time(self, utc_dt):
        """Convert UTC datetime sang local time của nhân viên"""
        import pytz
        tz = pytz.timezone(self.employee_id.tz or 'Asia/Ho_Chi_Minh')
        return utc_dt.replace(tzinfo=pytz.utc).astimezone(tz).replace(tzinfo=None)