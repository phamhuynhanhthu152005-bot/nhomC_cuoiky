from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import date


class ViolationReportWizard(models.TransientModel):
    _name = 'hr.violation.report.wizard'
    _description = 'Violation Report Wizard'

    date_from = fields.Date(
        'Tu ngay', required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date('Den ngay', required=True, default=fields.Date.today)
    department_ids = fields.Many2many('hr.department', string='Phong ban')
    employee_ids = fields.Many2many('hr.employee', string='Nhan vien cu the')
    violation_type = fields.Selection([
        ('all', 'Tat ca loai'),
        ('late', 'Di muon'),
        ('early_leave', 'Ve som'),
        ('absence', 'Vang mat'),
        ('insufficient_hours', 'Thieu gio'),
    ], default='all', string='Loai vi pham')
    severity = fields.Selection([
        ('all', 'Tat ca muc do'),
        ('minor', 'Nhe'),
        ('moderate', 'Vua'),
        ('major', 'Nang'),
    ], default='all', string='Muc do')
    state = fields.Selection([
        ('all', 'Tat ca trang thai'),
        ('confirmed', 'Da xac nhan'),
        ('penalized', 'Da tru luong'),
        ('pending_explanation', 'Cho giai trinh'),
    ], default='confirmed', string='Trang thai')
    include_waived = fields.Boolean('Bao gom vi pham da bo qua', default=False)
    report_type = fields.Selection([
        ('pdf', 'PDF - Bao cao chi tiet'),
        ('pivot', 'Mo Pivot view'),
    ], default='pdf', required=True, string='Dang xuat')

    preview_violation_count = fields.Integer(
        'So vi pham tim thay', compute='_compute_preview',
    )
    preview_total_deduction = fields.Float(
        'Tong khau tru (VND)', compute='_compute_preview',
    )
    preview_employee_count = fields.Integer(
        'So nhan vien lien quan', compute='_compute_preview',
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
            rec.preview_total_deduction = sum(violations.mapped('penalty_amount'))
            rec.preview_employee_count = len(violations.mapped('employee_id'))

    def _build_domain(self):
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.department_ids:
            domain.append(('employee_id.department_id', 'in', self.department_ids.ids))
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        if self.violation_type != 'all':
            domain.append(('violation_type', '=', self.violation_type))
        if self.severity != 'all':
            domain.append(('severity', '=', self.severity))
        if self.state != 'all':
            domain.append(('state', '=', self.state))
        elif not self.include_waived:
            domain.append(('state', '!=', 'waived'))
        return domain

    def action_generate_report(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError('"Tu ngay" phai nho hon hoac bang "Den ngay".')
        domain = self._build_domain()
        violations = self.env['hr.attendance.violation'].search(
            domain, order='employee_id, date'
        )
        if not violations:
            raise UserError(
                'Khong tim thay vi pham nao theo dieu kien da chon. '
                'Vui long kiem tra lai bo loc.'
            )
        if self.report_type == 'pivot':
            return {
                'name': f'Vi pham cham cong {self.date_from} - {self.date_to}',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.attendance.violation',
                'view_mode': 'pivot,graph,list',
                'domain': domain,
            }
        # PDF
        return {
            'type': 'ir.actions.act_window',
            'name': 'Danh sach vi pham',
            'res_model': 'hr.attendance.violation',
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_generate_penalty_summaries(self):
        self.ensure_one()
        domain = self._build_domain()
        domain.append(('state', '=', 'confirmed'))
        violations = self.env['hr.attendance.violation'].search(domain)
        months_years = set((v.month, v.year) for v in violations)
        employees = violations.mapped('employee_id')
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
                'title': 'Tao tong hop thanh cong',
                'message': f'Da tao {created} ban tong hop khau tru.',
                'type': 'success',
            }
        }
