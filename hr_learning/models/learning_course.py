# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LearningCourse(models.Model):
    """
    Bước 2: Course Recommendation
    Mỗi khóa học gắn với một Job Position (hr.job).
    """
    _name = 'learning.course'
    _description = 'Learning Course'
    _rec_name = 'name'
    _order = 'job_position_id, name'

    name = fields.Char(string='Course Name', required=True)
    provider = fields.Char(string='Provider')
    duration = fields.Float(string='Duration (Hours)', digits=(6, 2))
    description = fields.Text(string='Description')
    job_position_id = fields.Many2one(
        comodel_name='hr.job',
        string='Job Position',
        required=True,
        ondelete='restrict',
        index=True,
    )
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Action: mở POPUP form tạo Training Plan
    # ------------------------------------------------------------------
    def action_create_training_plan(self):
        self.ensure_one()
        ctx = self.env.context
        employee_id = ctx.get('active_employee_id')
        job_position_id = ctx.get('active_job_position_id') or self.job_position_id.id

        default_ctx = {
            'default_course_id': self.id,
            'default_job_position_id': job_position_id,
        }
        if employee_id:
            default_ctx['default_employee_id'] = employee_id

        # Lấy đúng popup view (priority=20, không có chatter)
        popup_view = self.env.ref(
            'custom_learning.view_training_plan_form_popup',
            raise_if_not_found=False,
        )

        action = {
            'name': 'Create Training Plan',
            'type': 'ir.actions.act_window',
            'res_model': 'training.plan',
            'view_mode': 'form',
            'target': 'new',
            'context': default_ctx,
        }
        if popup_view:
            action['views'] = [(popup_view.id, 'form')]

        return action
