# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal
from sql.conditionals import Case, Coalesce
from sql.aggregate import Min, Max
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import reduce_ids
from trytond.transaction import Transaction


__all__ = ['TestBuild', 'TestBuildResult', 'Component']
__metaclass__ = PoolMeta


class TestBuild(ModelSQL, ModelView):
    'Test Build'
    __name__ = 'project.test.build'

    execution = fields.DateTime('Execution', readonly=True)
    component = fields.Many2One('project.work.component', 'Component',
        required=True, readonly=False, select=True, ondelete='CASCADE')
    review = fields.Many2One('project.work.codereview', 'Review')
    branch = fields.Char('Branch', required=True)
    revision = fields.Char('Revision', required=True, readonly=True)
    revision_date = fields.DateTime('Revision Date')
    revision_author = fields.Char('Author')
    revision_description = fields.Char('Description')

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
        pool = Pool()
        Result = pool.get('project.test.build.result')
        cursor = Transaction().connection.cursor()
        in_max = 300

        build_ids = [g.id for g in builds]
        test_state = {}.fromkeys(build_ids, 'pass')
        flake_state = {}.fromkeys(build_ids, 'pass')
        coverage_state = {}.fromkeys(build_ids, 'ok')

        table = cls.__table__()
        result = Result.__table__()

        # TODO: Replace with grouped_slice
        for i in range(0, len(build_ids), in_max):
            sub_ids = build_ids[i:i + in_max]
            red_sql = reduce_ids(table.id, sub_ids)
            coverage = Case((table.coverage < Literal(50), 'error'),
                            (table.coverage < Literal(60), 'to_improve'),
                            (table.coverage < Literal(70), 'acceptable'),
                            else_='ok')
            coverage_query = table.select(table.id, coverage, where=red_sql)
            cursor.execute(*coverage_query)
            coverage_state.update(dict(cursor.fetchall()))
            for name in ('test_state', 'flake_state'):
                if name not in names:
                    continue

                if name == 'test_state':
                    types = ['unittest', 'scenario']
                else:
                    types = ['flake', 'pep8']
                numeric_state = Min(Case((result.state == Literal('error'), 0),
                        (result.state == Literal('fail'), 1),
                        else_=2))
                state = Case((numeric_state == Literal(0), 'error'),
                    (numeric_state == Literal(1), 'fail'),
                    else_='pass')
                query = result.join(table, condition=(
                        (table.id == result.build) &
                        result.type.in_(types))).select(table.id, state,
                            group_by=table.id)

                cursor.execute(*query)
                if name == 'test_state':
                    test_state.update(dict(cursor.fetchall()))
                else:
                    flake_state.update(dict(cursor.fetchall()))

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
            ], 'Type', required=True, readonly=True, select=True)
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
        cursor = Transaction().connection.cursor()

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
