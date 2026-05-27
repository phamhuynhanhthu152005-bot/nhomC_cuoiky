from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, datetime
import logging

_logger = logging.getLogger(__name__)


class HrAttendanceViolation(models.Model):
    _name = 'hr.attendance.violation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Attendance Violation'
    _order = 'date desc, employee_id'

    # ── Fields ─────────────────────────────────────────────────────────────
    attendance_id = fields.Many2one(
        'hr.attendance', 'Bản ghi chấm công'
    )
    employee_id = fields.Many2one(
        'hr.employee', 'Nhân viên', required=True, tracking=True
    )
    rule_id = fields.Many2one('hr.attendance.rule', 'Rule vi phạm')
    date = fields.Date('Ngày vi phạm', required=True)

    violation_type = fields.Selection([
        ('late', 'Đi muộn'),
        ('early_leave', 'Về sớm'),
        ('absence', 'Vắng mặt'),
        ('insufficient_hours', 'Thiếu giờ'),
    ], string='Loại vi phạm', required=True, tracking=True)

    severity = fields.Selection([
        ('minor', 'Nhẹ'),
        ('moderate', 'Vừa'),
        ('major', 'Nặng'),
    ], default='minor', tracking=True)

    deviation_minutes = fields.Float('Phút vi phạm')
    penalty_points = fields.Integer('Điểm vi phạm')
    penalty_amount = fields.Float('Tiền phạt (VNĐ)', tracking=True)

    state = fields.Selection([
        ('detected', 'Phát hiện'),
        ('pending_explanation', 'Chờ giải trình'),
        ('explained', 'Đã giải trình'),
        ('confirmed', 'Xác nhận vi phạm'),
        ('waived', 'Bỏ qua'),
        ('penalized', 'Đã trừ lương'),
    ], default='detected', tracking=True)

    explanation_id = fields.One2many(
        'hr.attendance.explanation', 'violation_id', 'Giải trình'
    )

    # Computed
    month = fields.Integer(compute='_compute_period', store=True)
    year = fields.Integer(compute='_compute_period', store=True)
    monthly_same_type_count = fields.Integer(
        compute='_compute_monthly_count', store=True
    )
    is_escalated = fields.Boolean(
        'Đã leo thang', default=False, tracking=True
    )
    department_id = fields.Many2one(
        'hr.department',
        related='employee_id.department_id',
        store=True,
        string='Phòng ban',
    )

    # ── Computed methods ────────────────────────────────────────────────────
    @api.depends('date')
    def _compute_period(self):
        for rec in self:
            if rec.date:
                rec.month = rec.date.month
                rec.year = rec.date.year
            else:
                rec.month = 0
                rec.year = 0

    @api.depends('employee_id', 'violation_type', 'month', 'year')
    def _compute_monthly_count(self):
        for rec in self:
            if not rec.employee_id or not rec.month:
                rec.monthly_same_type_count = 0
                continue
            rec.monthly_same_type_count = self.search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('violation_type', '=', rec.violation_type),
                ('month', '=', rec.month),
                ('year', '=', rec.year),
                ('state', 'not in', ['waived']),
            ])

    # ── Actions ────────────────────────────────────────────────────────────
    def action_request_explanation(self):
        """
        Chuyển vi phạm sang trạng thái chờ giải trình.
        Gửi activity đến nhân viên yêu cầu giải trình.
        """
        for rec in self:
            if rec.state != 'detected':
                continue
            rec.write({'state': 'pending_explanation'})

            # Tạo activity yêu cầu giải trình cho nhân viên
            deadline_hours = rec.rule_id.explanation_deadline_hours or 48
            deadline_date = fields.Date.today() + timedelta(
                hours=deadline_hours
            )
            if rec.employee_id.user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    note=(
                        f'Bạn có vi phạm chấm công ngày {rec.date}: '
                        f'{rec.get_violation_type_label()} '
                        f'({rec.deviation_minutes:.0f} phút). '
                        f'Vui lòng giải trình trước {deadline_date}.'
                    ),
                    user_id=rec.employee_id.user_id.id,
                    deadline=deadline_date,
                )

            # Thông báo cho nhân viên
            rec.message_post(
                body=(
                    f'<p>Vi phạm chấm công đã được ghi nhận:</p>'
                    f'<ul>'
                    f'<li>Loại: <b>{rec.get_violation_type_label()}</b></li>'
                    f'<li>Mức độ: <b>{rec.severity}</b></li>'
                    f'<li>Phút vi phạm: <b>{rec.deviation_minutes:.0f}</b></li>'
                    f'<li>Tiền phạt dự kiến: <b>{rec.penalty_amount:,.0f} VNĐ</b></li>'
                    f'</ul>'
                    f'<p>Vui lòng giải trình trong vòng '
                    f'{deadline_hours} giờ.</p>'
                ),
                partner_ids=(
                    [rec.employee_id.user_id.partner_id.id]
                    if rec.employee_id.user_id else []
                ),
            )

    def action_confirm(self):
        """Manager xác nhận vi phạm → kiểm tra escalation"""
        for rec in self:
            rec.write({'state': 'confirmed'})
            rec._check_escalation()

    def action_waive(self):
        """Manager bỏ qua vi phạm"""
        for rec in self:
            rec.write({'state': 'waived', 'penalty_amount': 0})
            # Đóng activity nếu còn
            try:
                rec.activity_feedback(
                    ['hr_attendance_control.activity_violation_explanation'],
                    feedback='Vi phạm đã được Manager bỏ qua.'
                )
            except Exception:
                pass
            rec.message_post(
                body='<p>Vi phạm đã được <b>bỏ qua</b>. Không trừ lương.</p>'
            )

    # ── Escalation ─────────────────────────────────────────────────────────
    def _check_escalation(self):
        """
        3 vi phạm nhẹ cùng loại trong tháng
        → tự động nâng severity thành major.
        """
        if self.severity != 'minor':
            return
        if self.monthly_same_type_count < 3:
            return
        if self.is_escalated:
            return

        self.write({
            'severity': 'major',
            'is_escalated': True,
        })

        # Gửi cảnh báo cho HR Manager group
        try:
            hr_manager_group = self.env.ref('hr.group_hr_manager')
            for user in hr_manager_group.users:
                self.activity_schedule(
                    'mail.mail_activity_data_warning',
                    note=(
                        f'Nhân viên {self.employee_id.name} đã vi phạm '
                        f'"{self.get_violation_type_label()}" '
                        f'{self.monthly_same_type_count} lần trong tháng '
                        f'{self.month}/{self.year}. '
                        f'Vi phạm tự động leo thang lên mức Nặng.'
                    ),
                    user_id=user.id,
                )
        except Exception as e:
            _logger.warning('Escalation notification failed: %s', e)

    def get_violation_type_label(self):
        labels = {
            'late': 'Đi muộn',
            'early_leave': 'Về sớm',
            'absence': 'Vắng mặt',
            'insufficient_hours': 'Thiếu giờ làm',
        }
        return labels.get(self.violation_type, self.violation_type)

    # ── Cronjob: phát hiện vắng mặt ────────────────────────────────────────
    @api.model
    def _cron_detect_absence(self):
        """
        Chạy mỗi sáng 05:00.
        Quét toàn bộ nhân viên xem hôm qua ai vắng mà không có phép.
        """
        from datetime import date as date_cls
        yesterday = fields.Date.today() - timedelta(days=1)
        weekday = yesterday.weekday()

        # Chỉ kiểm tra ngày làm việc thứ 2–6
        if weekday >= 5:
            _logger.info(
                'Absence detection skipped: %s is weekend.', yesterday
            )
            return

        # Tìm rule vắng mặt
        absence_rule = self.env['hr.attendance.rule'].search([
            ('violation_type', '=', 'absence'),
            ('is_active', '=', True),
        ], limit=1)

        if not absence_rule:
            _logger.warning(
                'No active absence rule found. Skipping absence detection.'
            )
            return

        # Lấy tất cả nhân viên đang có hợp đồng
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
        ])

        created_count = 0
        for employee in employees:
            # Kiểm tra lịch làm việc
            schedule = employee.resource_calendar_id
            if not schedule:
                continue

            # Kiểm tra hôm qua có phải ngày làm việc không
            attendance_lines = schedule.attendance_ids.filtered(
                lambda a: int(a.dayofweek) == weekday
            )
            if not attendance_lines:
                continue  # Không phải ngày làm việc theo lịch

            # Kiểm tra có attendance record không
            has_attendance = self.env['hr.attendance'].search_count([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', datetime.combine(
                    yesterday, datetime.min.time()
                )),
                ('check_in', '<', datetime.combine(
                    yesterday + timedelta(days=1), datetime.min.time()
                )),
            ])
            if has_attendance:
                continue

            # Kiểm tra có phép đã được duyệt không
            approved_leave = self.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', fields.Datetime.from_string(
                    f'{yesterday} 23:59:59'
                )),
                ('date_to', '>=', fields.Datetime.from_string(
                    f'{yesterday} 00:00:00'
                )),
            ])
            if approved_leave:
                continue

            # Kiểm tra đã có violation cho ngày này chưa
            existing = self.search_count([
                ('employee_id', '=', employee.id),
                ('date', '=', yesterday),
                ('violation_type', '=', 'absence'),
            ])
            if existing:
                continue

            # Tính tiền phạt
            penalty = self._calculate_absence_penalty(
                absence_rule, employee
            )

            # Tạo violation vắng mặt
            try:
                violation = self.create({
                    'employee_id': employee.id,
                    'rule_id': absence_rule.id,
                    'date': yesterday,
                    'violation_type': 'absence',
                    'severity': absence_rule.severity,
                    'deviation_minutes': 480,
                    'penalty_points': absence_rule.penalty_points,
                    'penalty_amount': penalty,
                    'state': 'detected',
                })
                # Tự động chuyển sang chờ giải trình
                violation.action_request_explanation()
                created_count += 1
                _logger.info(
                    'Absence violation created for %s on %s',
                    employee.name, yesterday
                )
            except Exception as e:
                _logger.error(
                    'Failed to create absence violation for %s: %s',
                    employee.name, str(e)
                )

        _logger.info(
            'Absence detection done: %d violations created for %s',
            created_count, yesterday
        )

    def _calculate_absence_penalty(self, rule, employee):
        """Tính tiền phạt vắng mặt dựa trên lương hợp đồng"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
        ], limit=1)

        if not contract:
            _logger.warning(
                'No active contract for %s, penalty set to 0.',
                employee.name
            )
            return 0.0

        monthly_wage = contract.wage
        daily_wage = monthly_wage / 26

        if rule.penalty_type == 'fixed':
            return rule.penalty_value
        elif rule.penalty_type == 'percent_daily':
            return daily_wage * rule.penalty_value / 100
        return 0.0