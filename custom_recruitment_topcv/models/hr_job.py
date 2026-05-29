from odoo import models, fields

class HrJob(models.Model):
    _inherit = 'hr.job'

    topcv_job_id = fields.Char(
        string="TopCV Job ID"
    )

    topcv_posted = fields.Boolean(
        string="Posted To TopCV",
        default=False
    )

    required_skills = fields.Text(
        string="Required Skills"
    )

    min_experience = fields.Integer(
        string="Minimum Experience"
    )

    jd_valid = fields.Boolean(
        string="JD Valid",
        default=False
    )


    def action_post_topcv(self):
        """Logic xử lý gọi API sang TopCV viết ở đây"""
        # Tạm thời để pass để Odoo không bắt lỗi trống hàm
        pass