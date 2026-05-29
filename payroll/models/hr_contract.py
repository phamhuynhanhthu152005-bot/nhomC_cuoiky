# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrVersion(models.Model):
    """
    Extend hr.version (which replaces hr.contract in Odoo 19 Community)
    to add payroll-specific fields.
    """

    _inherit = "hr.version"

    struct_id = fields.Many2one(
        "hr.payroll.structure",
        string="Salary Structure",
        groups="hr.group_hr_manager",
    )
    schedule_pay = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semi-annually", "Semi-annually"),
            ("annually", "Annually"),
            ("weekly", "Weekly"),
            ("bi-weekly", "Bi-weekly"),
            ("bi-monthly", "Bi-monthly"),
        ],
        string="Scheduled Pay",
        index=True,
        default="monthly",
        help="Defines the frequency of the wage payment.",
        groups="hr.group_hr_manager",
    )

    def get_all_structures(self):
        """
        @return: the structures linked to the given versions, ordered by
                 hierarchy (parent=False first, then first level children and
                 so on) and without duplicates
        """
        return self.struct_id.get_structure_with_parents()
