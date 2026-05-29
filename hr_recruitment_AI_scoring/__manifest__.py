{
    'name': 'AI-Powered HR Recruitment Scoring',
    'version': '1.0',
    'category': 'Human Resources/Recruitment',
    'summary': 'Smart CV Screening & Automated AI Scoring Based on Job Criteria',
    'description': 'Automate your recruitment process by scoring applicants CV against job requirements.',
    'depends': ['base', 'hr_recruitment'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_recruitment_criteria_views.xml',
        'views/hr_applicant_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}