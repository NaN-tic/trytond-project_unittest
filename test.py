#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.conditionals import Case, Coalesce
from sql.aggregate import Min, Max
import datetime
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


__all__ = ['TestBuildGroup', 'TestBuild', 'TestBuildResult', 'Component']
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
            ('sqlite', 'SQLite'),
            ('postgresql', 'PostgreSQL'),
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
            ('ok', 'Ok'),
            ('acceptable', 'Acceptable'),
            ('to_improve', 'To Improve'),
            ('error', 'Error'),
            ], 'Coverage State', select=True),
        'get_state', searcher='search_coverage_state')

    @classmethod
    def get_state(cls, groups, names):
        test_state = {}
        flake_state = {}
        coverage_state = {}

        for group in groups:
            test_state[group.id] = 'pass'
            flake_state[group.id] = 'pass'
            coverage_state[group.id] = 'pass'
            if any(x.test_state == 'error' for x in group.builds):
                test_state[group.id] = 'error'
            elif any(x.test_state == 'fail' for x in group.builds):
                test_state[group.id] = 'fail'
            if any(x.flake_state == 'error' for x in group.builds):
                flake_state[group.id] = 'error'
            elif any(x.flake_state == 'fail' for x in group.builds):
                flake_state[group.id] = 'fail'
            if any(b.coverage < 50 for b in group.builds):
                coverage_state[group.id] = 'error'
            elif any(b.coverage < 60 for b in group.builds):
                coverage_state[group.id] = 'to_improve'
            elif any(b.coverage < 70 for b in group.builds):
                coverage_state[group.id] = 'acceptable'
            else:
                coverage_state[group.id] = 'ok'

        result = {
            'coverage_state': coverage_state,
            'flake_state': flake_state,
            'test_state': test_state
        }

        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    @classmethod
    def search_state(cls, name, clause):
        pool = Pool()
        Build = pool.get('project.test.build')
        Result = pool.get('project.test.build.result')
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = Result.__table__()
        build = Build.__table__()
        if name == 'test_state':
            where = Coalesce(table.type, 'none').in_(['unittest', 'scenario',
                    'none'])
        elif name == 'flake_state':
            where = Coalesce(table.type, 'none').in_(['flake', 'pep8', 'none'])
        else:
            raise Exception('Bad argument')

        numeric_state = Min(Case((table.state == Literal('error'), 0),
                (table.state == Literal('fail'), 1),
                else_=2))
        state = Case((numeric_state == Literal(0), 'error'),
            (numeric_state == Literal(1), 'fail'),
            else_='pass')
        query = build.join(table, 'left', condition=(
                (build.id == table.build) & where)).select(build.group,
                    group_by=build.group, having=(Operator(state, value)))
        return [('id', 'in', query)]

    @classmethod
    def search_coverage_state(cls, name, clause):
        pool = Pool()
        Build = pool.get('project.test.build')
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = Build.__table__()
        coverage_state = Case((Min(table.coverage) < Literal(50), 'error'),
                        (Min(table.coverage) < Literal(60), 'to_improve'),
                        (Min(table.coverage) < Literal(70), 'acceptable'),
                        else_='ok')
        query = table.select(table.group,
            group_by=(table.group),
            having=(Operator(coverage_state, value)))
        return [('id', 'in', query)]

    @classmethod
    def delete_old_builds(cls, date=None):
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today() - relativedelta(months=1)
        if isinstance(date, datetime.date):
            date = datetime.datetime.combine(date, datetime.time(23, 59, 59))
        to_delete = cls.search([('end', '<=', date)])
        if to_delete:
            cls.delete(to_delete)


class TestBuild(ModelSQL, ModelView):
    'Test Build'
    __name__ = 'project.test.build'

    execution = fields.DateTime('Execution', readonly=True)
    group = fields.Many2One('project.test.build.group', 'Group', select=True,
        ondelete='CASCADE')
    component = fields.Many2One('project.work.component', 'Component',
        required=True, readonly=True, select=True, ondelete='CASCADE')
    review = fields.Many2One('project.work.codereview', 'Review')
    branch = fields.Char('Branch', required=True)
    revision = fields.Char('Revision', required=True, readonly=True)
    test = fields.One2Many('project.test.build.result', 'build', 'Tests',
        readonly=True)
    coverage = fields.Float('Coverage', digits=(16, 2),
        readonly=True)
    lines = fields.Integer('Lines', readonly=True)
    covered_lines = fields.Integer('Covered Lines', readonly=True,
        required=True)
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
            ('ok', 'Ok'),
            ('acceptable', 'Acceptable'),
            ('to_improve', 'To Improve'),
            ('error', 'Error'),
            ], 'Coverage State', select=True),
        'get_state', searcher='search_coverage_state')

    @classmethod
    def get_state(cls, builds, names):
        test_state = {}
        flake_state = {}
        coverage_state = {}

        for build in builds:
            test_lines = [x for x in build.test
                if x.type in ('unittest, scenario')]
            flake_lines = [x for x in build.test if x.type in ('flake, pep8')]

            test_state[build.id] = 'pass'
            flake_state[build.id] = 'pass'
            coverage_state[build.id] = 'pass'
            if any(x.state == 'error' for x in test_lines):
                test_state[build.id] = 'error'
            elif any(x.state == 'fail' for x in test_lines):
                test_state[build.id] = 'fail'
            if any(x.state == 'error' for x in flake_lines):
                flake_state[build.id] = 'error'
            elif any(x.state == 'fail' for x in flake_lines):
                flake_state[build.id] = 'fail'
            if build.coverage < 50:
                coverage_state[build.id] = 'error'
            elif build.coverage < 60:
                coverage_state[build.id] = 'to_improve'
            elif build.coverage < 70:
                coverage_state[build.id] = 'acceptable'
            else:
                coverage_state[build.id] = 'ok'

        result = {
            'coverage_state': coverage_state,
            'flake_state': flake_state,
            'test_state': test_state
        }

        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    @classmethod
    def search_coverage_state(cls, name, clause):
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = cls.__table__()
        coverage_state = Case((table.coverage < Literal(50), 'error'),
                        (table.coverage < Literal(60), 'to_improve'),
                        (table.coverage < Literal(70), 'acceptable'),
                        else_='ok')
        query = table.select(table.id,
            where=(Operator(coverage_state, value)))
        return [('id', 'in', query)]

    @classmethod
    def search_state(cls, name, clause):
        pool = Pool()
        Result = pool.get('project.test.build.result')
        _, operator, value = clause
        Operator = fields.SQL_OPERATORS[operator]
        table = Result.__table__()
        result = Result.__table__()
        if name == 'test_state':
            where = Coalesce(table.type, 'none').in_(['unittest', 'scenario',
                    'none'])
        elif name == 'flake_state':
            where = Coalesce(table.type, 'none').in_(['flake', 'pep8', 'none'])
        else:
            raise Exception('Bad argument')

        numeric_state = Min(Case((table.state == Literal('error'), 0),
                (table.state == Literal('fail'), 1),
                else_=2))
        state = Case((numeric_state == Literal(0), 'error'),
            (numeric_state == Literal(1), 'fail'),
            else_='pass')
        query = result.join(table, 'LEFT', condition=(
                (table.id == result.id) & where)).select(result.build,
                    group_by=result.build, having=(Operator(state, value)))
        return [('id', 'in', query)]


class TestBuildResult(ModelSQL, ModelView):
    'Test Build Result'
    __name__ = 'project.test.build.result'

    build = fields.Many2One('project.test.build', 'Build', required=True,
        readonly=True, select=True, ondelete='CASCADE')
    name = fields.Char('Name', required=True, readonly=True)
    type = fields.Selection([
            ('unittest', 'Unittest'),
            ('scenario', 'Scenario'),
            ('flake', 'Flake'),
            ('pep8', 'PEP8'),
            ('coverage', 'Coverage')
            ], 'Field Title', required=True, readonly=True, select=True)
    description = fields.Text('Description', readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('fail', 'Failed'),
            ('error', 'Error'),
            ('pass', 'Pass'),
            ], 'State', required=True, readonly=True, select=True)

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_type():
        return 'unittest'


class Component:
    __name__ = 'project.work.component'
    last_build = fields.Function(fields.Many2One('project.test.build',
            'Last Build'),
        'get_last_build')
    test_state = fields.Function(fields.Selection([
            ('', ''),
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Test State', select=True),
        'get_state')
    flake_state = fields.Function(fields.Selection([
            ('', ''),
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('error', 'Error'),
            ], 'Flake State', select=True),
        'get_state')
    coverage_state = fields.Function(fields.Selection([
            ('', ''),
            ('ok', 'Ok'),
            ('acceptable', 'Acceptable'),
            ('to_improve', 'To Improve'),
            ('error', 'Error'),
            ], 'Coverage State', select=True),
        'get_state')

    @classmethod
    def get_last_build(cls, components, name):
        pool = Pool()
        Build = pool.get('project.test.build')
        table = Build.__table__()
        table2 = Build.__table__()
        cursor = Transaction().cursor

        component_ids = [c.id for c in components]
        result = {}.fromkeys(component_ids, None)
        subquery = table2.select(table2.component,
            Max(table2.execution).as_('execution'),
            group_by=table2.component)

        query = table.join(subquery, condition=(
                (table.component == subquery.component) &
                (table.execution == subquery.execution))).select(
                    table.component, table.id,
                    where=table.component.in_(component_ids))
        cursor.execute(*query)
        result.update(dict(cursor.fetchall()))
        return result

    def get_state(self, name):
        if not self.last_build:
            return ''
        return getattr(self.last_build, name)
