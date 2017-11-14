import os
from collections import OrderedDict

from flask import Flask
from flask import render_template, flash, redirect, url_for, request
from flask import send_from_directory

import config as cfg
from ngsscriptlibrary import TargetDatabase, TargetAnnotation
from ngsscriptlibrary import SampleSheet

app = Flask(__name__)
app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'uploads'

HOME = cfg.HOME
TARGETS = cfg.TARGETS
DB = cfg.DB
MYSQLUSER = cfg.MYSQLUSER


def boolean_to_number(x):
    if x == 'False':
        x = 0
    elif not x:
        x = 0
    elif x == 'True':
        x = 1
    elif x:
        x = 1
    return x


@app.route('/')
@app.route('/index/')
def intro():
    return render_template('index.html')


@app.route('/index/database/')
def database_explained():
    return render_template('database_explanation.html')


@app.route('/nieuw/')
def new_menu():
    return render_template('new.html')


@app.route('/diagnostiek/')
def show_all_tests():
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    tests.sort()
    d = OrderedDict()
    for test in tests:
        d[test] = T.get_info_for_genesis(test)
    return render_template('showalltests.html', tests=d)


@app.route('/diagnostiek/<test>')
def show_testinfo(test):
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    if test not in tests:
        flash('{} niet gevonden'.format(test))
        return redirect(url_for('show_all_tests'))
    caps = T.get_all_captures_for_genesis(test)
    caps = [T.get_all_versions_for_capture(cap) for cap in caps]
    d = dict()
    for cap in caps:
        d[cap] = T.get_all_info_for_vcapture(test)

    for i in ['printcnv', 'mozaiekdetectie']:
        if d['capdb'][i] == 1:
            d['capdb'][i] = 'Ja'
        elif d['capdb'][i] == 0:
            d['capdb'][i] = 'Nee'
    if d['genes']['panelsize'] is None:
        d['genes']['panelsize'] = 0
    if d['capdb']['panel'] == 'False':
        d['capdb']['panel'] = 'Geen'
    if d['capdb']['panel'] == 'OVRv1':
        d['genes']['panelsize'] = 0
    if d['genes']['agenen'] == [] and d['genes']['cgenen'] == []:
        d['genes']['agenen'] = d['genes']['genen']

    return render_template('showtest.html', c=d['capdb'],
                           g=d['genes'], caps=caps)


@app.route('/diagnostiek/nieuw/')
def add_test():
    captures = TargetDatabase(DB).get_all_captures()
    return render_template('addtest.html', captures=captures)


@app.route('/captures/nieuw/linktest/', methods=['GET', 'POST'])
def link_test():
    T = TargetDatabase(DB)
    captures = T.get_all_captures()
    tests = T.get_all_tests()
    return render_template('addexistingtest.html',
                           captures=captures, tests=tests)


@app.route('/captures/nieuw/', methods=['GET', 'POST'])
def new_capture():
    if request.method == 'POST':
        T = TargetDatabase(DB)
        cap = request.form['capture']
        oid = request.form['oid']
        lot = request.form['lot']
        if 'verdund' in request.form:
            verdund = request.form['verdund']
        elif 'verdund' not in request.form:
            verdund = False
        verdund = boolean_to_number(verdund)
        sql = """INSERT INTO captures (capture, OID, lot, verdund)
                 VALUES ('{}', 'OID{}', {}, {})
                 """.format(cap, oid, lot, verdund)
        flash('{} toegevoegd aan database'.format(request.form['capture']))
        flash(sql)
        T.change(sql)
        return redirect(url_for('new_target', cap=cap, lot=lot,
                                oid=oid, verdund=verdund))

    return render_template('addcapture.html')


@app.route('/captures/nieuw/target/<cap>/',
           methods=['GET', 'POST'])
def new_target(cap):
    if request.method == 'POST':
        # T = TargetAnnotation(bedfile=targetfile, genes=genefile,
        #                      host='localhost', user=MYSQLUSER, db='annotation')
        pass
        # T = TargetDatabase(DB)
        # cap = request.form['capture']
        # oid = request.form['oid']
        # lot = request.form['lot']
        # verdund = request.form['verdund']
        # sql = "INSERT INTO captures {}, {}, {}, {}".format(cap, oid, lot, verdund)
        # T.change(sql)
    return render_template('addtargets.html', cap=cap, oid=oid,
                           lot=lot, verdund=verdund)


@app.route('/captures/<cap>', methods=['GET', 'POST'])
def show_tests_for_cap(cap):
    T = TargetDatabase(DB)
    tests = T.get_all_tests_for_capture(cap)
    lotnrs = T.get_all_lotnrs_for_capture(cap)
    if request.method == 'POST':
        sql = '''INSERT INTO captures
        (capture, OID, lot, verdund)
        SELECT DISTINCT capture, OID, {}, verdund
        FROM captures
        WHERE capture = '{}'
        '''.format(request.form['lotnr'], cap)
        T.change(sql)
        lotnrs = T.get_all_lotnrs_for_capture(cap)
        return render_template('showcap.html', cap=cap,
                               tests=tests, lotnrs=lotnrs)
    return render_template('showcap.html', cap=cap,
                           tests=tests, lotnrs=lotnrs)


@app.route('/createsamplesheet/', methods=['GET', 'POST'])
def upload_labexcel():
    if request.method == 'POST':
        if request.form['samples'] == '':
            flash('Geen input opgegeven')
            return render_template('uploadlabexcel.html')
        if request.form['serie'] == '':
            flash('Geen serienummer opgegeven')
            return render_template('uploadlabexcel.html')

        nullijst_todo = request.form['samples']
        if nullijst_todo:
            uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            with open(os.path.join(uploads, 'samplesheet.tmp'), 'w') as f:
                for line in nullijst_todo.split('\n'):
                    if line:
                        dnr, bc, test = line.split()
                        f.write('{}\t{}\t{}\n'.format(dnr, test, bc))

            S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'),
                            request.form['serie'],
                            os.path.join(uploads, 'SampleSheet.csv'))
            S.write_files()
            return redirect(url_for('uploaded_file',
                                    filename='SampleSheet.csv'))

    return render_template('uploadlabexcel.html')


@app.route('/createsamplesheet/created/<filename>')
def uploaded_file(filename):
    return render_template('download.html', filename=filename)


@app.route('/createsamplesheet/<path:filename>')
def download(filename):
    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    return send_from_directory(directory=uploads, filename=filename)


if __name__ == '__main__':
    app.run(debug=True)
