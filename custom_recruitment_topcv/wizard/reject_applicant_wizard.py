from odoo import models, fields, api

class RejectApplicantWizard(models.TransientModel):
    _name = 'reject.applicant.wizard'
    _description = 'Reject Applicant Wizard'

    reason = fields.Text()

    def action_confirm(self):

        applicant_ids = self.env.context.get(
            'active_ids'
        )

        applicants = self.env[
            'hr.applicant'
        ].browse(applicant_ids)

        for applicant in applicants:

            applicant.screening_status = 'rejected'