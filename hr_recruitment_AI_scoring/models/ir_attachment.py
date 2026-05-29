from odoo import models, api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super(IrAttachment, self).create(vals_list)
        for attachment in attachments:
            if attachment.res_model == 'hr.applicant' and attachment.res_id:
                applicant = self.env['hr.applicant'].browse(attachment.res_id)
                if applicant.exists() and applicant.scoring_state == 'not_scored':
                    applicant.action_score_cv()
        return attachments