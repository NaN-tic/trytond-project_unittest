# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import test
from . import work


def register():
    Pool.register(
        test.TestBuild,
        test.TestBuildResult,
        test.Component,
        work.Work,
        module='project_unittest', type_='model')
