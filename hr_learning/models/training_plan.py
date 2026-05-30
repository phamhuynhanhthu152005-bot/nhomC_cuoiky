# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TrainingPlan(models.Model):
    """
    Bước 3: Training Plan
    Kế hoạch đào tạo gắn nhân viên với khóa học.

    Kế thừa mail.thread để tracking thay đổi status (không hiện chatter trong UI).
    Tất cả trường mail.activity.mixin bị ẩn hoàn toàn khỏi view – chỉ dùng nội bộ.
    """
    _name = 'training.plan'
    _description = 'Training Plan'
    _rec_name = 'plan_name'
    _order = 'start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ------------------------------------------------------------------
    # BLOCK 1: Thông tin Training Plan
    # ------------------------------------------------------------------
    plan_name = fields.Char(
        string='Plan Name',
        compute='_compute_plan_name',
        store=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        ondelete='cascade',
        index=True,
    )
    job_position_id = fields.Many2one(
        comodel_name='hr.job',
        string='Job Position',
        related='employee_id.job_id',
        store=True,
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='learning.course',
        string='Course',
        required=True,
        tracking=True,
        ondelete='restrict',
    )

    # ------------------------------------------------------------------
    # BLOCK 2: Schedule
    # ------------------------------------------------------------------
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ('draft',       'Draft'),
            ('in_progress', 'In Progress'),
            ('completed',   'Completed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # BLOCK 3: Training Notification
    # ------------------------------------------------------------------
    notification_subject = fields.Char(
        string='Notification Subject',
        help='Tiêu đề thông báo gửi cho nhân viên',
    )
    notification_content = fields.Html(
        string='Notification Content',
        help='Nội dung thông báo gửi cho nhân viên',
        sanitize=True,
    )
    notification_date = fields.Date(
        string='Notification Date',
        help='Ngày gửi thông báo đào tạo',
    )

    # ------------------------------------------------------------------
    # BLOCK 4: Notes
    # ------------------------------------------------------------------
    notes = fields.Text(
        string='Notes',
        help='Ghi chú nội bộ về kế hoạch đào tạo',
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('employee_id', 'course_id')
    def _compute_plan_name(self):
        for rec in self:
            emp = rec.employee_id.name or ''
            course = rec.course_id.name or ''
            if emp and course:
                rec.plan_name = '%s – %s' % (emp, course)
            else:
                rec.plan_name = emp or course or 'New Training Plan'

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(
                    'End Date phải lớn hơn hoặc bằng Start Date.'
                )

    @api.constrains('notification_date', 'start_date')
    def _check_notification_date(self):
        for rec in self:
            if (rec.notification_date and rec.start_date
                    and rec.notification_date > rec.start_date):
                raise ValidationError(
                    'Notification Date không được sau Start Date.'
                )

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------
    def action_set_in_progress(self):
        self.write({'status': 'in_progress'})

    def action_set_completed(self):
        self.write({'status': 'completed'})

    def action_reset_draft(self):
        self.write({'status': 'draft'})
