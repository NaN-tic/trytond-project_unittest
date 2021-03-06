# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .test import *
from .work import *

def register():
    Pool.register(
        TestBuildGroup,
        TestBuild,
        TestBuildResult,
        Component,
        Work,
        module='project_unittest', type_='model')
