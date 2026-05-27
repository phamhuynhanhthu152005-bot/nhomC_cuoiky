from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date


class ViolationReportWizard(models.TransientModel):
    """
    Wizard xuất báo cáo vi phạm chấm công.
    Cho phép HR chọn khoảng thời gian, phòng ban,
    loại vi phạm rồi xuất PDF hoặc xem pivot.
    """
    _name = 'hr.violation.report.wizard'
    _description = 'Violation Report Wizard'

    # ── Bộ lọc ─────────────────────────────────────────────────────────────
    date_from = fields.Date(
        'Từ ngày',
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        'Đến ngày',
        required=True,
        default=fields.Date.today,
    )
    department_ids = fields.Many2many(
        'hr.department',
        string='Phòng ban',
        help='Để trống = toàn công ty',
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Nhân viên cụ thể',
        help='Để trống = tất cả nhân viên',
    )
    violation_type = fields.Selection([
        ('all', 'Tất cả loại'),
        ('late', 'Đi muộn'),
        ('early_leave', 'Về sớm'),
        ('absence', 'Vắng mặt'),
        ('insufficient_hours', 'Thiếu giờ'),
    ], string='Loại vi phạm', default='all')
    severity = fields.Selection([
        ('all', 'Tất cả mức độ'),
        ('minor', 'Nhẹ'),
        ('moderate', 'Vừa'),
        ('major', 'Nặng'),
    ], string='Mức độ', default='all')
    state = fields.Selection([
        ('all', 'Tất cả trạng thái'),
        ('confirmed', 'Đã xác nhận'),
        ('penalized', 'Đã trừ lương'),
        ('pending_explanation', 'Chờ giải trình'),
    ], string='Trạng thái', default='confirmed')

    # ── Tùy chọn xuất ──────────────────────────────────────────────────────
    report_type = fields.Selection([
        ('pdf', 'PDF — Báo cáo chi tiết'),
        ('pivot', 'Mở Pivot view'),
    ], string='Dạng xuất', default='pdf', required=True)
    include_waived = fields.Boolean(
        'Bao gồm vi phạm đã bỏ qua',
        default=False,
    )

    # ── Preview thống kê nhanh ─────────────────────────────────────────────
    preview_violation_count = fields.Integer(
        'Số vi phạm tìm thấy',
        compute='_compute_preview',
    )
    preview_total_deduction = fields.Float(
        'Tổng khấu trừ (VNĐ)',
        compute='_compute_preview',
    )
    preview_employee_count = fields.Integer(
        'Số nhân viên liên quan',
        compute='_compute_preview',
    )

    @api.depends(
        'date_from', 'date_to', 'department_ids',
        'employee_ids', 'violation_type', 'severity', 'state'
    )
    def _compute_preview(self):
        for rec in self:
            domain = rec._build_domain()
            violations = self.env['hr.attendance.violation'].search(domain)
            rec.preview_violation_count = len(violations)
            rec.preview_total_deduction = sum(
                violations.mapped('penalty_amount')
            )
            rec.preview_employee_count = len(
                violations.mapped('employee_id')
            )

    def _build_domain(self):
        """Xây dựng domain tìm kiếm dựa trên các filter đã chọn"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]

        if self.department_ids:
            domain.append(
                ('employee_id.department_id', 'in', self.department_ids.ids)
            )
        if self.employee_ids:
            domain.append(
                ('employee_id', 'in', self.employee_ids.ids)
            )
        if self.violation_type != 'all':
            domain.append(('violation_type', '=', self.violation_type))
        if self.severity != 'all':
            domain.append(('severity', '=', self.severity))

        # Xử lý state filter
        if self.state != 'all':
            domain.append(('state', '=', self.state))
        elif not self.include_waived:
            domain.append(('state', '!=', 'waived'))

        return domain

    def action_generate_report(self):
        """Xuất báo cáo theo loại đã chọn"""
        self.ensure_one()

        if self.date_from > self.date_to:
            raise UserError('"Từ ngày" phải nhỏ hơn hoặc bằng "Đến ngày".')

        domain = self._build_domain()
        violations = self.env['hr.attendance.violation'].search(
            domain, order='employee_id, date'
        )

        if not violations:
            raise UserError(
                'Không tìm thấy vi phạm nào theo điều kiện đã chọn. '
                'Vui lòng kiểm tra lại bộ lọc.'
            )

        if self.report_type == 'pdf':
            # Xuất PDF
            return self.env.ref(
                'hr_attendance_control.action_report_violation_summary'
            ).report_action(violations.ids, data={
                'date_from': str(self.date_from),
                'date_to': str(self.date_to),
                'total_deduction': sum(violations.mapped('penalty_amount')),
                'employee_count': len(violations.mapped('employee_id')),
            })

        else:
            # Mở pivot view với domain đã filter
            return {
                'name': (
                    f'Vi phạm chấm công '
                    f'{self.date_from} → {self.date_to}'
                ),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.attendance.violation',
                'view_mode': 'pivot,graph,tree',
                'domain': domain,
                'context': {
                    'pivot_measures': ['penalty_amount', 'penalty_points'],
                    'pivot_row_groupby': ['employee_id'],
                    'pivot_column_groupby': ['violation_type'],
                },
            }

    def action_generate_penalty_summaries(self):
        """
        Tạo penalty summary cho tất cả nhân viên
        có vi phạm trong khoảng thời gian đã chọn.
        Dùng khi HR muốn chạy tổng hợp thủ công
        thay vì đợi cronjob.
        """
        self.ensure_one()
        domain = self._build_domain()
        domain.append(('state', '=', 'confirmed'))
        violations = self.env['hr.attendance.violation'].search(domain)

        employees = violations.mapped('employee_id')
        months_years = set(
            (v.month, v.year) for v in violations
        )
        created = 0
        for employee in employees:
            for month, year in months_years:
                existing = self.env['hr.attendance.penalty.summary'].search([
                    ('employee_id', '=', employee.id),
                    ('month', '=', month),
                    ('year', '=', year),
                ])
                if not existing:
                    summary = self.env['hr.attendance.penalty.summary'].create({
                        'employee_id': employee.id,
                        'month': month,
                        'year': year,
                    })
                    summary.action_confirm()
                    created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tạo tổng hợp thành công',
                'message': f'Đã tạo {created} bản tổng hợp khấu trừ.',
                'type': 'success',
            }
        }