# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class SkillMaster(models.Model):
    """
    Bước 1: Job Search
    Tham chiếu hr.employee để tìm nhân viên và job position.
    KHÔNG lưu bản sao dữ liệu HR – chỉ dùng Many2one.
    """
    _name = 'skill.master'
    _description = 'Job Search'
    _rec_name = 'name'
    _order = 'employee_id'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
    )
    job_position_id = fields.Many2one(
        comodel_name='hr.job',
        string='Job Position',
        related='employee_id.job_id',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )
    notes = fields.Text(string='Notes')

    course_count = fields.Integer(
        string='Available Courses',
        compute='_compute_course_count',
        store=False,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('employee_id', 'employee_id.name')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.employee_id.name if rec.employee_id else '/'

    @api.depends('job_position_id')
    def _compute_course_count(self):
        """
        Đếm courses theo tên Job Position (ilike) để tránh lỗi duplicate hr.job ID.
        Xem thêm: _get_matching_job_ids()
        """
        for rec in self:
            if rec.job_position_id:
                matching_ids = rec._get_matching_job_ids()
                rec.course_count = self.env['learning.course'].search_count([
                    ('job_position_id', 'in', matching_ids),
                ])
            else:
                rec.course_count = 0

    # ------------------------------------------------------------------
    # Helper: tìm tất cả hr.job có cùng tên với job_position_id của employee
    # ------------------------------------------------------------------
    def _get_matching_job_ids(self):
        """
        Vấn đề gốc rễ:
        -  hr.employee.job_id  có thể trỏ tới hr.job ID=1  (tạo từ HR module)
        -  learning.course.job_position_id trỏ tới hr.job ID=10 (tạo từ data.xml)
        -  Cả 2 đều có name='Business Analyst' nhưng khác ID.

        Giải pháp:
        -  Tìm TẤT CẢ hr.job records có cùng tên (case-insensitive).
        -  Dùng danh sách IDs này để filter courses → đảm bảo không bỏ sót.

        Returns:
            list[int]: Danh sách hr.job IDs có cùng tên với job_position_id của employee.
        """
        self.ensure_one()
        if not self.job_position_id:
            return []
        job_name = self.job_position_id.name.strip()
        matching_jobs = self.env['hr.job'].search([
            ('name', '=ilike', job_name),
        ])
        return matching_jobs.ids

    # ------------------------------------------------------------------
    # Action: mở Course Recommendation lọc theo job position name
    # ------------------------------------------------------------------
    def action_view_recommended_courses(self):
        self.ensure_one()
        if not self.job_position_id:
            raise UserError(
                'Nhân viên "%s" chưa có Job Position.\n'
                'Vui lòng vào HR → Employees → cập nhật Job Position trước.'
                % self.employee_id.name
            )

        # Lấy tất cả hr.job IDs có cùng tên → tránh vấn đề duplicate records
        matching_job_ids = self._get_matching_job_ids()

        # Kiểm tra có courses nào không (để báo lỗi sớm nếu cần)
        course_count = self.env['learning.course'].search_count([
            ('job_position_id', 'in', matching_job_ids),
        ])

        if course_count == 0:
            raise UserError(
                'Không tìm thấy khóa học nào cho Job Position "%s".\n\n'
                'Nguyên nhân có thể:\n'
                '• Chưa có khóa học nào được tạo cho vị trí này.\n'
                '• Khóa học tồn tại nhưng gắn với Job Position trùng tên khác ID.\n\n'
                'Vui lòng vào menu Course Recommendation → kiểm tra cột Job Position.'
                % self.job_position_id.name
            )

        return {
            'name': 'Khóa học dành cho: %s' % self.job_position_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'learning.course',
            'view_mode': 'list,form',
            # Dùng 'in' thay '=' để bắt tất cả hr.job records cùng tên
            'domain': [('job_position_id', 'in', matching_job_ids)],
            'context': {
                'default_job_position_id': self.job_position_id.id,
                'active_employee_id': self.employee_id.id,
                'active_job_position_id': self.job_position_id.id,
            },
        }
