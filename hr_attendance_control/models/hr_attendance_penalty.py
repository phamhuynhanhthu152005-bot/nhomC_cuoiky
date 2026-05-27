# Part of hr_attendance_control module
import logging
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HrAttendancePenaltySummary(models.Model):
    """
    Tổng hợp khấu trừ vi phạm chấm công theo nhân viên theo tháng.
    Được tạo tự động bởi cronjob cuối tháng hoặc khi HR
    chạy wizard tổng hợp.
    Dùng để push deduction vào hr.payslip.
    """
    _name = 'hr.attendance.penalty.summary'
    _description = 'Attendance Penalty Monthly Summary'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'
    _order = 'year desc, month desc, employee_id'

    # ── Khoá chính logic ───────────────────────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    month = fields.Integer('Tháng', required=True)
    year = fields.Integer('Năm', required=True)

    # ── Thống kê ───────────────────────────────────────────────────────────
    total_violations = fields.Integer(
        'Tổng số vi phạm',
        compute='_compute_stats',
        store=True,
    )
    minor_count = fields.Integer(
        'Vi phạm nhẹ',
        compute='_compute_stats',
        store=True,
    )
    moderate_count = fields.Integer(
        'Vi phạm vừa',
        compute='_compute_stats',
        store=True,
    )
    major_count = fields.Integer(
        'Vi phạm nặng',
        compute='_compute_stats',
        store=True,
    )
    total_points = fields.Integer(
        'Tổng điểm vi phạm',
        compute='_compute_stats',
        store=True,
    )
    total_deduction = fields.Float(
        'Tổng khấu trừ (VNĐ)',
        compute='_compute_stats',
        store=True,
        tracking=True,
    )
    late_minutes_total = fields.Float(
        'Tổng phút đi muộn',
        compute='_compute_stats',
        store=True,
    )
    absence_days = fields.Integer(
        'Ngày vắng mặt không phép',
        compute='_compute_stats',
        store=True,
    )

    # ── Trạng thái ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Đã xác nhận'),
        ('pushed', 'Đã đẩy vào lương'),
    ], default='draft', tracking=True)

    pushed_to_payroll = fields.Boolean(
        'Đã đẩy vào Payroll',
        default=False,
        tracking=True,
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        'Phiếu lương liên quan',
        readonly=True,
    )

    # ── Display ────────────────────────────────────────────────────────────
    # KHÔNG dùng display_name vì đây là field reserved của Odoo
    # Đổi sang penalty_display_name để tránh xung đột
    penalty_display_name = fields.Char(
        string='Tên hiển thị',
        compute='_compute_penalty_display_name',
        store=True,
    )
    violation_ids = fields.One2many(
        'hr.attendance.violation',
        compute='_compute_violation_ids',
        string='Chi tiết vi phạm',
    )

    # ── Computed fields ────────────────────────────────────────────────────
    @api.depends('employee_id', 'month', 'year')
    def _compute_penalty_display_name(self):
        for rec in self:
            emp = rec.employee_id.name or ''
            rec.penalty_display_name = f'{emp} — {rec.month:02d}/{rec.year}'

    def _compute_violation_ids(self):
        for rec in self:
            rec.violation_ids = self.env['hr.attendance.violation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('month', '=', rec.month),
                ('year', '=', rec.year),
                ('state', '=', 'confirmed'),
            ])

    @api.depends('employee_id', 'month', 'year')
    def _compute_stats(self):
        for rec in self:
            violations = self.env['hr.attendance.violation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('month', '=', rec.month),
                ('year', '=', rec.year),
                ('state', '=', 'confirmed'),
            ])

            rec.total_violations = len(violations)
            rec.minor_count = len(violations.filtered(
                lambda v: v.severity == 'minor'
            ))
            rec.moderate_count = len(violations.filtered(
                lambda v: v.severity == 'moderate'
            ))
            rec.major_count = len(violations.filtered(
                lambda v: v.severity == 'major'
            ))
            rec.total_points = sum(violations.mapped('penalty_points'))
            rec.total_deduction = sum(violations.mapped('penalty_amount'))
            rec.late_minutes_total = sum(
                v.deviation_minutes for v in violations
                if v.violation_type == 'late'
            )
            rec.absence_days = len(violations.filtered(
                lambda v: v.violation_type == 'absence'
            ))

    # ── Constraints (Odoo 19 — dùng @api.constrains thay _sql_constraints) ─
    @api.constrains('employee_id', 'month', 'year')
    def _check_unique_employee_month_year(self):
        """
        Đảm bảo mỗi nhân viên chỉ có 1 bản tổng hợp cho mỗi tháng.
        Thay thế _sql_constraints không còn được hỗ trợ trong Odoo 19.
        """
        for rec in self:
            duplicate = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('month', '=', rec.month),
                ('year', '=', rec.year),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    f'Nhân viên {rec.employee_id.name} đã có bản tổng hợp '
                    f'cho tháng {rec.month:02d}/{rec.year} rồi!'
                )

    # ── Actions ────────────────────────────────────────────────────────────
    def action_confirm(self):
        """Xác nhận tổng hợp — sẵn sàng push vào Payroll"""
        for rec in self:
            if rec.total_violations == 0:
                _logger.info(
                    'Penalty summary %s has no violations, skipping confirm.',
                    rec.penalty_display_name
                )
                continue
            rec.write({'state': 'confirmed'})

    def action_push_to_payroll(self):
        """
        Tìm payslip của nhân viên trong tháng tương ứng
        và inject deduction line vào payslip.
        """
        self.ensure_one()

        # ── Guard checks ──────────────────────────────────────────────────
        if self.pushed_to_payroll:
            raise UserError(
                'Bản tổng hợp này đã được đẩy vào Payroll rồi. '
                'Không thể đẩy lại.'
            )
        if self.state != 'confirmed':
            raise UserError(
                'Vui lòng xác nhận bản tổng hợp trước khi đẩy vào Payroll.'
            )
        if self.total_deduction <= 0:
            raise UserError(
                'Không có khoản khấu trừ nào để đẩy vào Payroll.'
            )

        # ── Tìm payslip tháng tương ứng ──────────────────────────────────
        payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['draft', 'verify']),
            ('date_from', '<=', date(self.year, self.month, 28)),
            ('date_to', '>=', date(self.year, self.month, 1)),
        ], limit=1)

        if not payslip:
            raise UserError(
                f'Không tìm thấy phiếu lương (trạng thái Nháp hoặc Đang xử lý) '
                f'của {self.employee_id.name} '
                f'cho tháng {self.month:02d}/{self.year}.\n'
                f'Vui lòng tạo phiếu lương trước rồi thử lại.'
            )

        # ── Inject deduction line vào payslip ─────────────────────────────
        self._inject_deduction_to_payslip(payslip)

        # ── Đánh dấu violations là penalized ─────────────────────────────
        violations = self.env['hr.attendance.violation'].search([
            ('employee_id', '=', self.employee_id.id),
            ('month', '=', self.month),
            ('year', '=', self.year),
            ('state', '=', 'confirmed'),
        ])
        violations.write({'state': 'penalized'})

        # ── Cập nhật trạng thái summary ───────────────────────────────────
        self.write({
            'pushed_to_payroll': True,
            'state': 'pushed',
            'payslip_id': payslip.id,
        })

        _logger.info(
            'Attendance deduction %.0f VND pushed to payslip %s for employee %s',
            self.total_deduction,
            payslip.name,
            self.employee_id.name,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đẩy vào Payroll thành công',
                'message': (
                    f'Đã tạo khoản khấu trừ '
                    f'{self.total_deduction:,.0f} VNĐ '
                    f'vào phiếu lương của {self.employee_id.name} '
                    f'tháng {self.month:02d}/{self.year}.'
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def _inject_deduction_to_payslip(self, payslip):
        """
        Tạo payslip line khấu trừ vi phạm chấm công.
        Tìm salary rule có code ATTEND_DEDUCT,
        nếu chưa có thì tự tạo.
        """
        # Tìm salary rule ATTEND_DEDUCT
        deduction_rule = self.env['hr.salary.rule'].search([
            ('code', '=', 'ATTEND_DEDUCT'),
        ], limit=1)

        if not deduction_rule:
            # Tìm category DED (Deduction)
            ded_category = self.env['hr.salary.rule.category'].search([
                ('code', '=', 'DED'),
            ], limit=1)

            if not ded_category:
                # Tạo category nếu chưa có
                ded_category = self.env['hr.salary.rule.category'].create({
                    'name': 'Deductions',
                    'code': 'DED',
                })

            # Tìm structure của payslip để gán rule vào
            struct = payslip.struct_id
            if not struct:
                raise UserError(
                    'Phiếu lương chưa có Salary Structure. '
                    'Vui lòng chọn Structure trước khi đẩy khấu trừ.'
                )

            deduction_rule = self.env['hr.salary.rule'].create({
                'name': 'Khấu trừ vi phạm chấm công',
                'code': 'ATTEND_DEDUCT',
                'category_id': ded_category.id,
                'struct_id': struct.id,
                'sequence': 200,
                'amount_select': 'fix',
                'amount_fix': 0.0,
                'active': True,
            })
            _logger.info(
                'Created salary rule ATTEND_DEDUCT id=%d', deduction_rule.id
            )

        # Kiểm tra đã có line này trong payslip chưa (tránh duplicate)
        existing_line = self.env['hr.payslip.line'].search([
            ('payslip_id', '=', payslip.id),
            ('code', '=', 'ATTEND_DEDUCT'),
        ], limit=1)

        if existing_line:
            # Cập nhật số tiền nếu đã tồn tại
            existing_line.write({
                'amount': -self.total_deduction,
                'total': -self.total_deduction,
            })
            _logger.info(
                'Updated existing ATTEND_DEDUCT line on payslip %s',
                payslip.name
            )
        else:
            # Tạo mới payslip line
            self.env['hr.payslip.line'].create({
                'payslip_id': payslip.id,
                'name': (
                    f'Khấu trừ vi phạm chấm công '
                    f'(tháng {self.month:02d}/{self.year})'
                ),
                'code': 'ATTEND_DEDUCT',
                'salary_rule_id': deduction_rule.id,
                'category_id': deduction_rule.category_id.id,
                'sequence': 200,
                'amount': -self.total_deduction,
                'total': -self.total_deduction,
                'quantity': 1.0,
                'rate': 100.0,
            })
            _logger.info(
                'Created ATTEND_DEDUCT line %.0f VND on payslip %s',
                self.total_deduction, payslip.name
            )

    # ── Scheduled action ───────────────────────────────────────────────────
    @api.model
    def _cron_generate_monthly_summary(self):
        """
        Chạy ngày 1 hàng tháng lúc 06:00.
        Tự động tạo bản tổng hợp cho tháng vừa rồi.
        """
        today = date.today()

        # Tính tháng vừa rồi
        if today.month == 1:
            target_month = 12
            target_year = today.year - 1
        else:
            target_month = today.month - 1
            target_year = today.year

        _logger.info(
            'Running monthly penalty summary for %02d/%d',
            target_month, target_year
        )

        # Lấy tất cả nhân viên có vi phạm confirmed trong tháng đó
        violations = self.env['hr.attendance.violation'].search([
            ('month', '=', target_month),
            ('year', '=', target_year),
            ('state', '=', 'confirmed'),
        ])

        if not violations:
            _logger.info(
                'No confirmed violations found for %02d/%d, skipping.',
                target_month, target_year
            )
            return

        employees = violations.mapped('employee_id')
        created_count = 0

        for employee in employees:
            # Kiểm tra đã có bản tổng hợp chưa
            existing = self.search([
                ('employee_id', '=', employee.id),
                ('month', '=', target_month),
                ('year', '=', target_year),
            ])
            if existing:
                _logger.info(
                    'Summary already exists for %s %02d/%d, skipping.',
                    employee.name, target_month, target_year
                )
                continue

            try:
                summary = self.create({
                    'employee_id': employee.id,
                    'month': target_month,
                    'year': target_year,
                })
                summary.action_confirm()
                created_count += 1
                _logger.info(
                    'Created penalty summary for %s: %.0f VND deduction',
                    employee.name, summary.total_deduction
                )
            except Exception as e:
                _logger.error(
                    'Failed to create penalty summary for %s: %s',
                    employee.name, str(e)
                )
                continue

        _logger.info(
            'Monthly penalty summary done: created %d records for %02d/%d',
            created_count, target_month, target_year
        )