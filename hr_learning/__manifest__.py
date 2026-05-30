# -*- coding: utf-8 -*-
{
    'name': 'Custom Learning',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Learning',
    'summary': 'Job Search, Course Recommendation & Training Plan',
    'description': """
        Custom Learning Module for Odoo 19
        ====================================
        Step 1: Job Search       - Browse employees and their job positions
        Step 2: Course Recommendation - Courses filtered by job position
        Step 3: Training Plan    - Create and track training plans
    """,
    'author': 'Custom',
    'depends': ['hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/learning_course_data.xml',
        'views/skill_master_views.xml',
        'views/learning_course_views.xml',
        'views/training_plan_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

