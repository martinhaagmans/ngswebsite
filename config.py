import sys
import os

HOME = os.path.expanduser('~')
ngslibloc = os.path.join(HOME, 'Documents', 'ngsscriptlibrary')
TARGETS = os.path.join(HOME, 'Documents', 'ngstargets')
DB = os.path.join(TARGETS, 'varia', 'captures.sqlite')
MYSQLUSER = 'manager'
sys.path.insert(0, ngslibloc)
