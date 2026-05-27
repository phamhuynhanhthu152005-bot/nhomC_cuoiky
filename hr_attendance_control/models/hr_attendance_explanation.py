from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


class HrAttendanceExplanation(models.Model):
    """
    Model giải trình vi phạm chấm công.
    Mỗi violation có thể có tối đa 1 explanation.
    Nhân viên submit → Manager review → accept/reject.
    """
    _name = 'hr.attendance.explanation'
    _description = 'Attendance Violation Explanation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'violation_id'
    _order = 'submitted_at desc'

    # ── Quan hệ ────────────────────────────────────────────────────────────
    violation_id = fields.Many2one(
        'hr.attendance.violation',
        string='Vi phạm liên quan',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên',
        related='violation_id.employee_id',
        store=True,
        readonly=True,
    )

    # ── Nội dung giải trình ────────────────────────────────────────────────
    explanation_text = fields.Text(
        string='Nội dung giải trình',
        required=True,
        tracking=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'explanation_attachment_rel',
        'explanation_id',
        'attachment_id',
        string='Tài liệu đính kèm',
        help='Ảnh, file PDF làm bằng chứng (phiếu khám bệnh, biên bản tai nạn...)',
    )

    # ── Thời gian ──────────────────────────────────────────────────────────
    submitted_at = fields.Datetime(
        string='Thời điểm gửi',
        readonly=True,
    )
    deadline = fields.Datetime(
        string='Hạn giải trình',
        readonly=True,
        tracking=True,
    )
    is_overdue = fields.Boolean(
        string='Quá hạn',
        compute='_compute_is_overdue',
        store=True,
    )

    # ── Trạng thái ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Đang soạn'),
        ('submitted', 'Đã gửi — Chờ review'),
        ('accepted', 'Được chấp nhận'),
        ('rejected', 'Bị từ chối'),
    ], default='draft', string='Trạng thái', tracking=True)

    # ── Phản hồi của Manager ───────────────────────────────────────────────
    manager_note = fields.Text(
        string='Ghi chú của Manager',
        tracking=True,
    )
    reviewed_by_id = fields.Many2one(
        'res.users',
        string='Người review',
        readonly=True,
    )
    reviewed_at = fields.Datetime(
        string='Thời điểm review',
        readonly=True,
    )

    # ── Computed ───────────────────────────────────────────────────────────
    @api.depends('deadline')
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_overdue = bool(
                rec.deadline and rec.deadline < now
                and rec.state in ('draft', 'submitted')
            )

    # ── Constraints ────────────────────────────────────────────────────────
    @api.constrains('violation_id')
    def _check_unique_explanation(self):
        """Mỗi violation chỉ được có một explanation"""
        for rec in self:
            duplicate = self.search([
                ('violation_id', '=', rec.violation_id.id),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    'Vi phạm này đã có giải trình rồi. '
                    'Vui lòng sửa giải trình hiện tại thay vì tạo mới.'
                )

    @api.constrains('state', 'deadline')
    def _check_submit_deadline(self):
        """Không cho phép submit sau khi quá hạn"""
        for rec in self:
            if rec.state == 'submitted' and rec.is_overdue:
                raise ValidationError(
                    f'Đã quá hạn giải trình ({rec.deadline}). '
                    'Không thể gửi giải trình sau thời hạn quy định.'
                )

    # ── Actions ────────────────────────────────────────────────────────────
    def action_submit(self):
        """Nhân viên gửi giải trình"""
        self.ensure_one()

        if not self.explanation_text or not self.explanation_text.strip():
            raise UserError('Vui lòng nhập nội dung giải trình trước khi gửi.')

        if self.is_overdue:
            raise UserError(
                f'Đã quá hạn giải trình ({self.deadline}). '
                'Không thể gửi giải trình sau thời hạn quy định.'
            )

        self.write({
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        })

        # Cập nhật trạng thái violation
        self.violation_id.write({'state': 'explained'})

        # Thông báo cho Manager
        manager = self.employee_id.parent_id
        if manager and manager.user_id:
            self.violation_id.activity_schedule(
                'hr_attendance_control.activity_violation_explanation',
                note=(
                    f'Nhân viên {self.employee_id.name} đã gửi giải trình '
                    f'cho vi phạm ngày {self.violation_id.date}. '
                    f'Vui lòng xem xét và phê duyệt.'
                ),
                user_id=manager.user_id.id,
                deadline=fields.Date.today() + timedelta(days=1),
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gửi giải trình thành công',
                'message': 'Giải trình của bạn đã được gửi đến Manager. '
                           'Bạn sẽ nhận thông báo khi có kết quả.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_accept(self):
        """Manager chấp nhận giải trình → waive violation"""
        self.ensure_one()
        self._check_manager_permission()

        self.write({
            'state': 'accepted',
            'reviewed_by_id': self.env.user.id,
            'reviewed_at': fields.Datetime.now(),
        })

        # Waive violation → không trừ lương
        self.violation_id.action_waive()

        # Thông báo cho nhân viên
        if self.employee_id.user_id:
            self.message_post(
                body=(
                    f'<p>Giải trình của bạn đã được <b>chấp nhận</b> bởi '
                    f'{self.env.user.name}.</p>'
                    f'<p>Vi phạm ngày {self.violation_id.date} '
                    f'sẽ không bị trừ lương.</p>'
                ),
                partner_ids=[(4, self.employee_id.user_id.partner_id.id)],
            )

        # Đóng activity giải trình
        self.violation_id.activity_feedback(
            ['hr_attendance_control.activity_violation_explanation'],
            feedback=f'Giải trình được chấp nhận bởi {self.env.user.name}.',
        )

    def action_reject(self):
        """Manager từ chối giải trình → confirm violation"""
        self.ensure_one()
        self._check_manager_permission()

        if not self.manager_note or not self.manager_note.strip():
            raise UserError(
                'Vui lòng nhập lý do từ chối vào trường '
                '"Ghi chú của Manager" trước khi từ chối.'
            )

        self.write({
            'state': 'rejected',
            'reviewed_by_id': self.env.user.id,
            'reviewed_at': fields.Datetime.now(),
        })

        # Confirm violation → sẽ bị trừ lương
        self.violation_id.action_confirm()

        # Thông báo cho nhân viên
        if self.employee_id.user_id:
            self.message_post(
                body=(
                    f'<p>Giải trình của bạn đã bị <b>từ chối</b> bởi '
                    f'{self.env.user.name}.</p>'
                    f'<p><b>Lý do:</b> {self.manager_note}</p>'
                    f'<p>Vi phạm ngày {self.violation_id.date} '
                    f'sẽ được tính vào khấu trừ lương tháng này.</p>'
                ),
                partner_ids=[(4, self.employee_id.user_id.partner_id.id)],
            )

    def _check_manager_permission(self):
        """Kiểm tra user hiện tại có quyền Manager không"""
        if not self.env.user.has_group(
            'hr_attendance_control.group_attendance_manager'
        ):
            raise UserError(
                'Chỉ HR Manager mới có quyền phê duyệt hoặc từ chối giải trình.'
            )

    # ── Scheduled action: tự động confirm khi hết hạn ─────────────────────
    @api.model
    def _cron_auto_confirm_expired(self):
        """
        Chạy mỗi 6 giờ.
        Vi phạm có deadline giải trình đã qua mà nhân viên
        không gửi giải trình → tự động confirm.
        """
        now = fields.Datetime.now()

        # Vi phạm đang chờ giải trình và đã quá deadline
        expired_violations = self.env['hr.attendance.violation'].search([
            ('state', 'in', ['detected', 'pending_explanation']),
        ])

        for violation in expired_violations:
            rule = violation.rule_id
            if not rule.requires_explanation:
                # Rule không yêu cầu giải trình → confirm ngay
                violation.action_confirm()
                continue

            # Tính deadline dựa trên ngày phát hiện + deadline_hours của rule
            detection_time = violation.create_date or fields.Datetime.now()
            deadline = detection_time + timedelta(
                hours=rule.explanation_deadline_hours or 48
            )

            if now > deadline:
                # Quá hạn mà không có giải trình
                existing_explanation = self.search([
                    ('violation_id', '=', violation.id),
                ])
                if not existing_explanation:
                    violation.action_confirm()
                    violation.message_post(
                        body=(
                            f'Vi phạm tự động xác nhận do hết hạn giải trình '
                            f'({deadline.strftime("%d/%m/%Y %H:%M")}).'
                        )
                    )