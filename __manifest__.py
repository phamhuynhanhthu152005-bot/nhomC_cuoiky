{
    'name': 'Recruitment TopCV Integration',

    'version': '1.0',

    'summary': 'Auto collect CV from TopCV',

    'category': 'Human Resources',

    'author': 'Pham Thu',

    'depends': ['base', 'hr', 'hr_recruitment', 'mail'], # Bắt buộc phải có 'hr_recruitment'

    'data': [

       # 'security/security.xml',
        'security/ir.model.access.csv',

        'data/mail_template.xml',
        'data/cron.xml',

        'views/hr_job_views.xml',
       # 'views/hr_applicant_views.xml',
        'views/menu.xml',

       # 'views/reject_applicant_wizard_view.xml',
    ],

    'installable': True,

    'application': True,
}