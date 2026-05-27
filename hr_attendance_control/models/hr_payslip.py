from odoo import api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    attendance_deduction_amount = fields.Float(
        string='Khấu trừ vi phạm chấm công',
        compute='_compute_attendance_deduction',
        store=True,
    )
    attendance_violation_count = fields.Integer(
        compute='_compute_attendance_deduction', store=True
    )

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_attendance_deduction(self):
        for rec in self:
            violations = self.env['hr.attendance.violation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'confirmed'),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
            ])
            rec.attendance_deduction_amount = sum(violations.mapped('penalty_amount'))
            rec.attendance_violation_count = len(violations)

    def action_payslip_done(self):
        """
        Override action_payslip_done để:
        1. Inject deduction line vào payslip
        2. Đánh dấu các violation là 'penalized'
        """
        result = super().action_payslip_done()

        for rec in self:
            violations = self.env['hr.attendance.violation'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'confirmed'),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
            ])

            if violations and rec.attendance_deduction_amount > 0:
                self._create_attendance_deduction_line(rec, rec.attendance_deduction_amount)
                # Đánh dấu đã xử lý
                violations.write({'state': 'penalized'})

        return result

    def _create_attendance_deduction_line(self, payslip, amount):
        """
        Tạo payslip line khấu trừ vi phạm chấm công.
        Tìm hoặc tạo salary rule 'ATTENDANCE_DEDUCTION'.
        """
        deduction_rule = self.env['hr.salary.rule'].search([
            ('code', '=', 'ATTEND_DEDUCT'),
        ], limit=1)

        if not deduction_rule:
            # Auto-create salary rule nếu chưa có
            deduction_rule = self.env['hr.salary.rule'].create({
                'name': 'Khấu trừ vi phạm chấm công',
                'code': 'ATTEND_DEDUCT',
                'category_id': self.env.ref('hr_payroll.DED').id,
                'sequence': 200,
                'amount_select': 'fix',
                'amount_fix': 0,
                'struct_id': payslip.struct_id.id,
            })

        self.env['hr.payslip.line'].create({
            'payslip_id': payslip.id,
            'name': f'Khấu trừ vi phạm chấm công ({payslip.date_from} - {payslip.date_to})',
            'code': 'ATTEND_DEDUCT',
            'salary_rule_id': deduction_rule.id,
            'category_id': deduction_rule.category_id.id,
            'sequence': 200,
            'amount': -amount,  # âm vì là deduction
            'total': -amount,
            'quantity': 1,
            'rate': 100,
        })