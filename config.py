import sys
import os

HOME = os.path.expanduser('~')
ngslibloc = os.path.join(HOME, 'Documents', 'GitHub', 'ngsscriptlibrary')
TARGETS = os.path.join(HOME, 'Documents', 'GitHub', 'ngstargets')
DB = os.path.join(TARGETS, 'varia', 'captures.sqlite')
MYSQLUSER = 'manager'
sys.path.insert(0, ngslibloc)

USER = 'connoiseur'
PASSWORD = 'a0179a631c45a16e015959be3e92b7b28edbdd5e2e0c796670b7f2a423fc8019:6e2f40d5b428438c8cb5530fa7e3f7e2'
