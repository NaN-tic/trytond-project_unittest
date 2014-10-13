#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval



__all__ = ['TestBuildGroup', 'TestBuild', 'TestBuildResult']
__metaclass__ = PoolMeta


class TestBuildGroup(ModelSQL, ModelView):
    'Test Build Group'
    __name__ = 'project.test.build.group'

    name = fields.Char('Name', required=True, select=True)
    start = fields.DateTime('Start', readonly=True)
    end = fields.DateTime('End', readonly=True)
    builds = fields.One2Many('project.test.build', 'group', 'Builds',
        readonly=True)
    db_type = fields.Selection([
            ('sqlite','SqLite'),
            ('postgresql', 'Postgresql'),
            ], 'db_type', required=True, readonly=True, select=True)

    failfast = fields.Boolean('Fail Fast', readonly=True)
    reviews = fields.Boolean('Include Reviews', readonly=True)
    development = fields.Boolean('Development', readonly=True)

    test_state = fields.Function(fields.Selection([
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Test State', select=True),
        'get_state', searcher='search_state')
    flake_state = fields.Function(fields.Selection([
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Flake State', select=True),
        'get_state', searcher='search_state')
    coverage_state = fields.Function(fields.Selection([
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Coverage State', select=True),
        'get_state', searcher='search_state')


    @classmethod
    def get_state(cls, groups, names):
        test_state={}
        flake_state={}
        coverage_state={}

        for group in groups:
            test_state[group.id] = 'pass'
            flake_state[group.id] = 'pass'
            coverage_state[group.id] = 'pass'
            for x in group.builds:
                if x.test_state in ('fail','error'):
                     test_state[group.id] = 'error'
                     break
            for x in group.builds:
                if x.flake_state in ('fail','error'):
                     flake_state[group.id] = 'error'
                     break
            for x in group.builds:
                if x.coverage_state in ('fail','error'):
                     coverage_state[group.id] = 'error'
                     break

        result = {
            'coverage_state': coverage_state,
            'flake_state': flake_state,
            'test_state': test_state
        }

        for key in result.keys():
            if key not in names:
                del result[key]
        return result


class TestBuild(ModelSQL, ModelView):
    '''Test Build'''
    __name__ = 'project.test.build'

    execution = fields.DateTime('Execution', readonly=True)
    group = fields.Many2One('project.test.build.group', 'Group', select=True)
    component = fields.Many2One('project.work.component', 'Component',
        required=True, readonly=True, select=True, ondelete='CASCADE')
    review = fields.Many2One('project.work.codereview', 'Review')
    branch = fields.Char('Branch', required=True)
    revision = fields.Char('Revision', required=True, readonly=True)

    test = fields.One2Many('project.test.build.result', 'build', 'Tests')
    coverage = fields.Float('Coverage', digits=(16, Eval('unit_digits', 2)),
        readonly=True)
    lines = fields.Integer('Lines', readonly=True)
    covered_lines = fields.Integer('Covered Lines', readonly=True)
    test_state = fields.Function(fields.Selection([
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Test State', select=True),
        'get_state', searcher='search_state')
    flake_state = fields.Function(fields.Selection([
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Flake State', select=True),
        'get_state', searcher='search_state')
    coverage_state = fields.Function(fields.Selection([
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Coverage State', select=True),
        'get_state', searcher='search_state')


    @classmethod
    def get_state(cls, builds, names):
        test_state={}
        flake_state={}
        coverage_state={}

        for build in builds:
            test_lines = [x for x in build.test if x.type in ('unittest, scenario')]
            flake_lines = [x for x in build.test if x.type in ('flake, pep8')]

            test_state[build.id] = 'pass'
            flake_state[build.id] = 'pass'
            coverage_state[build.id] = 'pass'
            for x in test_lines:
                if x.state in ('fail','error'):
                     test_state[build.id] = 'error'
                     break
            for x in flake_lines:
                if x.state in ('fail','error'):
                     flake_state[build.id] = 'error'
                     break
            if build.coverage < 80:
                coverage_state[build.id] = 'error'


        result = {
            'coverage_state': coverage_state,
            'flake_state': flake_state,
            'test_state': test_state
        }

        for key in result.keys():
            if key not in names:
                del result[key]
        return result

class TestBuildResult(ModelSQL, ModelView):
    '''Test Build Result'''
    __name__ = 'project.test.build.result'

    build = fields.Many2One('project.test.build', 'Build', required=True,
        readonly=True, select=True)
    name = fields.Char('Name', required=True, readonly=True)
    type = fields.Selection([
            ('unittest','Unittest'),
            ('scenario','Scenario'),
            ('flake','Flake'),
            ('pep8','PEP8'),
            ('coverage','Coverage')
            ], 'Field Title', required=True, readonly=True, select=True,
        help='')
    description = fields.Text('Description', readonly=True)

    state = fields.Selection([
            ('draft', 'Draft'),
            ('fail', 'Failed'),
            ('error', 'Error'),
            ('pass', 'Pass'),
            ], 'State', required=True, readonly=True, select=True)




