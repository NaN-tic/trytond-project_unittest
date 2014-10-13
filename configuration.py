# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, ModelSingleton
import os
import subprocess

__all__ = ['Configuration','ConfigurationComponent']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    '''Product Configuration'''
    __name__ = 'project.test.configuration'


    test_component = fields.Many2One('project.component', 'Repository', required=True)
    directory = fields.Char('Directory', required=True)
    client_components = fields.Many2Many(
        'project.test.configuration-project.component',
        'configuration', 'component', 'Client Components')




class ConfigurationComponent(ModelSQL):
    'Configuration - Component'
    __name__ = 'project.test.configuration-project.component'

    configuration = fields.Many2One('project.test.configuration',
        'Configuration', required=True, select=True)
    component = fields.Many2One('project.component', 'Component',
        required=True, select=True)

