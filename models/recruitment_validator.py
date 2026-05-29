from odoo import api, models
from odoo.exceptions import ValidationError

class RecruitmentValidator(models.Model):
    _inherit = 'hr.job'

    @api.constrains('description')

    def _check_description(self):

        for rec in self:

            if not rec.description:

                raise ValidationError(
                    "Job Description không được để trống"
                )

            if len(rec.description) < 100:

                raise ValidationError(
                    "JD phải lớn hơn 100 ký tự"
                )

            rec.jd_valid = True

def action_post_topcv(self):

    self.ensure_one()

    if not self.jd_valid:

        raise ValidationError(
            "JD chưa hợp lệ"
        )

    payload = {
        'title': self.name,
        'description': self.description,
        'skills': self.required_skills,
        'experience': self.min_experience,
    }

    response = self.env[
        'topcv.api'
    ].post_job(payload)

    self.topcv_job_id = response.get('job_id')

    self.topcv_posted = True