import os
import re
import json
import hashlib
import uuid
from functools import wraps
from collections import OrderedDict

from flask import Flask
from flask import render_template, flash, redirect, url_for, request, session
from flask import send_from_directory

import config as cfg
from ngsscriptlibrary import TargetDatabase
from ngsscriptlibrary import TargetAnnotation
from ngsscriptlibrary import SampleSheet
from ngsscriptlibrary import get_picard_header, boolean_to_number

app = Flask(__name__)
app.secret_key = 'super secrefft keyse7'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'uploads'

HOME = cfg.HOME
TARGETS = cfg.TARGETS
DB = cfg.DB
MYSQLUSER = cfg.MYSQLUSER
check_user = cfg.USER
check_passwd = cfg.PASSWORD


def hash_password(password):
    salt = uuid.uuid4().hex
    return (hashlib.sha256(salt.encode()
            + password.encode()).hexdigest()
            + ':'
            + salt)


def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return (password == hashlib.sha256(salt.encode()
            + user_password.encode()).hexdigest())


def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in') is not None:
            return f(*args, **kwargs)
        else:
            flash('Moet ingelogd zijn.', 'error')
            return redirect(url_for('do_connaiseur_login'))
    return decorated_function


@app.route('/')
def intro():
    return render_template('index.html')


@app.route('/login/', methods=['GET', 'POST'])
def do_connaiseur_login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if user == check_user and check_password(check_passwd, pwd):
            session['logged_in'] = True
            return redirect(url_for('new_menu'))
        else:
            flash('Verkeerde gebruiker of wachtwoord.', 'error')
            return render_template('login.html')
    return render_template('login.html')


@app.route('/database/')
def database_explained():
    return render_template('explanation_database.html')


@app.route('/pipeline/')
def pipeline_explained():
    return render_template('explanation_pipeline.html')


@app.route('/naamgeving/')
def nomenclature_explained():
    return render_template('explanation_nomenclature.html')


@app.route('/nieuw/')
@logged_in
def new_menu():
    return render_template('connoimenu.html')


@app.route('/diagnostiek/')
def show_all_tests():
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    tests.sort()
    tmp = dict()
    capture_test = dict()

    for test in tests:
        tmp[test] = T.get_info_for_genesis(test)
        cap = tmp[test]['capture']
        capture_test[cap] = test
    d = OrderedDict()
    captures = list(capture_test.keys())
    captures.sort()
    for cap in captures:
        for test in tests:
            if tmp[test]['capture'] == cap:
                d[test] = tmp[test]
    return render_template('showalltests.html', tests=d)


@app.route('/diagnostiek/<genesis>')
def show_testinfo(genesis):
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    if genesis not in tests:
        flash('{} niet gevonden'.format(genesis))
        return redirect(url_for('show_all_tests'))

    d = dict()
    d['captures'] = dict()
    d['pakketten'] = dict()
    d['panels'] = dict()

    caps = T.get_all_captures_for_genesis(genesis)
    caps = [T.get_all_versions_for_capture(cap) for cap in caps]
    for cap in caps:
        for vcap in cap:
            d['captures'][vcap] = T.get_all_info_for_vcapture(vcap)

    pakketten = T.get_all_pakketten_for_genesis(genesis)
    pakketten = [T.get_all_versions_for_pakket(p) for p in pakketten]
    for p in pakketten:
        for vp in p:
            d['pakketten'][vp] = T.get_all_info_for_vpakket(vp)

    panels = T.get_all_panels_for_genesis(genesis)
    panels = [T.get_all_versions_for_panel(p) for p in panels]
    for p in panels:
        if p is None:
            continue
        for vp in p:
            d['panels'][vp] = T.get_all_info_for_vpanel(vp)
    todo_list = T.get_info_for_genesis(genesis)
    return render_template('showtest.html', info=d, todo=todo_list)


@app.route('/diagnostiek/nieuw/', methods=['GET', 'POST'])
def add_test():
    captures = TargetDatabase(DB).get_all_captures()
    return render_template('addtest.html', captures=captures)


@app.route('/captures/<cap>')
def show_tests_for_cap(cap):
    T = TargetDatabase(DB)
    info = T.get_all_info_for_vcapture(cap)
    genesis = T.get_all_genesiscodes_for_vcapture(cap)
    oid = list()
    lot = list()
    for tup in info:
        o, l, verdund, size = tup
        oid.append(o)
        lot.append(l)

    return render_template('showcap.html', oid=oid, lot=lot, genesis=genesis,
                           verdund=verdund, size=size, cap=cap)


@app.route('/captures/link/', methods=['GET', 'POST'])
@logged_in
def link_capture():
    T = TargetDatabase(DB)
    captures = T.get_all_captures()
    gcodes = T.get_all_tests()
    if request.method == 'POST':
        capture = request.form['capture']
        gcodes = request.form.getlist('test')
        for gc in gcodes:
            sql = """UPDATE genesis
            SET capture='{}'
            WHERE genesis='{}'
            """.format(capture, gc)
            T.change(sql)
        return redirect(url_for('show_all_tests'))
    return render_template('linkcapture.html', captures=captures, tests=gcodes)


@app.route('/captures/nieuw/', methods=['GET', 'POST'])
@logged_in
def new_capture():
    if request.method == 'POST':
        T = TargetDatabase(DB)
        cap = request.form['capture'].lower()
        oid = request.form['oid']
        lot = request.form['lot']
        vcap = re.search(r'v\d+$', cap)
        if vcap is not None:
            re.sub(r'v\d+$', '', cap)
        if 'verdund' in request.form:
            verdund = request.form['verdund']
        elif 'verdund' not in request.form:
            verdund = False
        cap = cap.upper()
        verdund = boolean_to_number(verdund)
        allcaptures = T.get_all_captures()
        if cap not in allcaptures:
            versie = 1
        elif cap in allcaptures:
            versies = T.get_all_versions_for_capture(cap)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1
        sql = """INSERT INTO captures (capture, versie, OID, lot, verdund, grootte)
                 VALUES ('{}', {}, {}, {}, {}, 0)
                 """.format(cap, versie, oid, lot, verdund)
        flash('{} toegevoegd aan database'.format(request.form['capture']))
        flash(sql)
        T.change(sql)
        return redirect(url_for('new_target', cap='{}v{}'.format(cap, versie)))

    return render_template('addcapture.html')


@app.route('/captures/nieuw/target/<cap>', methods=['GET', 'POST'])
@logged_in
def new_target(cap):
    if request.method == 'POST':
        capture, versie = cap.split('v')
        targetrepo = os.path.join(TARGETS, capture)
        if not os.path.isdir(targetrepo):
            os.system('mkdir -p {}'.format(targetrepo))
        genelist = request.form['genen'].split()
        targetfile = request.files['targetfile']
        name = '{}_exonplus20.bed'.format(cap)
        targetfile.save(os.path.join(targetrepo, name))
        targetfile = os.path.join(targetrepo, name)
        T = TargetAnnotation(bedfile=targetfile, genes=genelist,
                             host='localhost', user=MYSQLUSER, db='annotation')
        notfound, notrequested = T.report_genecomp()
        annotated_bed = T.annotate_bed_and_filter_genes()
        annotated_bed_file = os.path.join(targetrepo,
                                          name.replace('.bed', '.annotated'))
        capsize = 0
        with open(annotated_bed_file, 'w') as f:
            for line in annotated_bed:
                chromosome, start, end, gene = line
                f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                  end, gene))
                size = int(end) - int(start)
                capsize += size

        generegion_file = os.path.join(targetrepo,
                                       '{}_generegions.bed'.format(cap))
        with open(generegion_file, 'w') as f:
            for gene in genelist:
                for region in T.get_region(gene):
                    chromosome, start, end = region
                    f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                      end, gene))

        picardheader = get_picard_header()
        picard_file = os.path.join(targetrepo,
                                   '{}_targets.interval_list'.format(cap))
        with open(picard_file, 'w') as f:
            for line in picardheader:
                f.write(line)
            for line in annotated_bed:
                chromosome, start, end, gene = line
                f.write('{}\t{}\t{}\t+\t{}\n'.format(chromosome,
                                                     start, end, cap))
        sql = '''UPDATE captures
        SET grootte={}, genen='{}'
        WHERE (capture='{}' AND versie={})
        '''.format(capsize, json.dumps(genelist), capture, versie)
        TargetDatabase(DB).change(sql)
        return render_template('newcapreport.html', notfound=notfound,
                               notrequested=notrequested, cap=cap)

    return render_template('addtargets.html', cap=cap)


@app.route('/pakketten/nieuw/', methods=['GET', 'POST'])
@logged_in
def new_pakket():
    if request.method == 'POST':
        if request.form['naam'] == '':
            flash('Geen pakket opgegeven')
            return redirect(url_for('new_pakket'))
        if request.form['genen'] == '':
            flash('Geen genen opgegeven')
            return redirect(url_for('new_pakket'))
        pakket = request.form['naam'].lower()
        genen = request.form['genen'].split()

        vpakket = re.search(r'v\d+$', pakket)
        if vpakket is not None:
            re.sub(r'v\d+$', '', pakket)
        pakket = pakket.upper()
        T = TargetDatabase(DB)
        allpakketten = T.get_all_pakketten()
        if pakket not in allpakketten:
            versie = 1
        elif pakket in allpakketten:
            versies = T.get_all_versions_for_pakket(pakket)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1
        sql = """INSERT INTO pakketten (pakket, versie, genen)
                 VALUES ('{}', {}, '{}')
                 """.format(pakket, versie,  json.dumps(genen))
        T.change(sql)
        vcapture = T.get_capture_for_pakket(pakket)
        capture, capversie = vcapture.split('v')
        if capture == pakket:
            sql = """UPDATE pakketten
            SET grootte=(SELECT grootte
                         FROM captures
                         WHERE (capture='{}' AND versie={}))
            WHERE (pakket='{}' and versie={})
            """.format(capture, int(capversie), pakket, versie)
            T.change(sql)
        else:
            targetrepo = os.path.join(TARGETS, capture)
            if not os.path.isdir(targetrepo):
                raise OSError('{} does not exist.'.format(targetrepo))
            targetrepo = os.path.join(TARGETS, capture, pakket)
            os.system('mkdir -p {}'.format(targetrepo))
            annoted_bed = os.path.join(TARGETS, capture,
                                       '{}_exonplus20.annotated'.format(vcapture)
                                       )
            cap_generegions = os.path.join(TARGETS, capture,
                                           '{}_generegions.bed'.format(vcapture))
            pakketbed = os.path.join(targetrepo,
                                     '{}v{}_exonplus20.bed'.format(pakket,
                                                                   versie))
            annotated_pakketbed = os.path.join(targetrepo,
                                               '{}v{}_exonplus20.annotated'.format(pakket,
                                                                                   versie))

            pakket_generegs = os.path.join(targetrepo,
                                           '{}v{}_generegions.bed'.format(pakket,
                                                                          versie))
            TA = TargetAnnotation(annoted_bed)
            size = 0
            with open(pakketbed, 'w') as f, open(annotated_pakketbed, 'w') as fa:
                for line in TA.bed:
                    chromosome, start, end, gen = line
                    if gen in genen:
                        fa.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                           end, gen))
                        f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                          end, gen))
                        size += int(end) - int(start)
                for gen in genen:
                    if ':' in gen and '-' in gen:
                        chromosome, startend = chromosome.split(':')
                        start, end = startend.split('-')
                        f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                          end, 'EXTRA'))
                        size += int(end) - int(start)

            with open(cap_generegions) as f, open(pakket_generegs, 'w') as fout:
                for line in f:
                    chromosome, start, end, gen = line.split()
                    if gen in genen:
                        fout.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                             end, gen))
            sql = """UPDATE pakketten
            SET grootte={}
            WHERE (pakket='{}' AND versie={})
            """.format(size, pakket, int(versie))
            T.change(sql)
        return redirect(url_for('show_all_tests'))
    return render_template('addpakket.html')


@app.route('/panels/nieuw/', methods=['GET', 'POST'])
@logged_in
def new_panel():
    if request.method == 'POST':
        if request.form['naam'] == '':
            flash('Geen panel opgegeven')
            return redirect(url_for('new_panel'))
        if request.form['genen'] == '':
            flash('Geen genen opgegeven')
            return redirect(url_for('new_panel'))
        panel = request.form['naam'].lower()
        genen = request.form['genen'].split()

        vpanel = re.search(r'v\d+$', panel)
        if vpanel is not None:
            re.sub(r'v\d+$', '', panel)
            re.sub(r'typea$', '', panel)
        panel = panel.upper()
        T = TargetDatabase(DB)
        allpanels = T.get_all_panels()
        if panel not in allpanels:
            versie = 1
        elif panel in allpanels:
            versies = T.get_all_versions_for_panel(panel)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1
        sql = """INSERT INTO panels (panel, versie, genen)
                 VALUES ('{}', {}, '{}')
                 """.format(panel, versie,  json.dumps(genen))
        T.change(sql)
        vpakket = T.get_pakket_for_panel(panel)
        pakket, versiepakket = vpakket.split('v')
        vcapture = T.get_capture_for_pakket(pakket)
        capture, versiecapture = vcapture.split('v')
        annoted_bed = os.path.join(TARGETS, capture,
                                   '{}_exonplus20.annotated'.format(vcapture))

        if capture == pakket:
            targetrepo = os.path.join(TARGETS, capture)
        elif capture != pakket:
            targetrepo = os.path.join(TARGETS, capture, pakket)
        if not os.path.isdir(targetrepo):
            raise OSError('{} does not exist.'.format(targetrepo))
        corepanels = os.path.join(targetrepo, 'corepanels')
        if not os.path.isdir(corepanels):
            os.system('mkdir -p {}'.format(corepanels))

        panelbed = os.path.join(corepanels,
                                '{}typeAv{}.bed'.format(panel,
                                                        versie))
        TA = TargetAnnotation(annoted_bed)
        size = 0
        with open(panelbed, 'w') as f:
            for line in TA.bed:
                chromosome, start, end, gen = line
                if gen in genen:
                    f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                      end, gen))
                    size += int(end) - int(start)
            for gen in genen:
                if ':' in gen and '-' in gen:
                    chromosome, startend = chromosome.split(':')
                    start, end = startend.split('-')
                    f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start,
                                                      end, 'EXTRA'))
                    size += int(end) - int(start)
        sql = """UPDATE panels
        SET grootte={}
        WHERE (panel='{}' AND versie={})
        """.format(size, panel, int(versie))
        T.change(sql)
        return redirect(url_for('show_all_tests'))
    return render_template('addpanel.html')


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


@app.route('/faciliteit/', methods=['GET', 'POST'])
def linda_samplesheet():
    if request.method == 'POST':
        if request.form['samples'] == '':
            flash('Geen input opgegeven', 'error')
            return render_template('faciliteit.html')
        if request.form['readlength'] == '':
            flash('Geen read lengte opgegeven', 'error')
            return render_template('faciliteit.html')
        if request.form['serie'] == '':
            serie = 'Nvt'
        else:
            serie = request.form['serie']

        readlength = request.form['readlength']
        todo = request.form['samples']

        uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        with open(os.path.join(uploads, 'samplesheet.tmp'), 'w') as f:
            for line in todo.split('\n'):
                if line:
                    dnr, bc = line.split()
                    f.write('{}\t{}\t{}\n'.format(dnr, serie, bc))

        S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'),
                        serie,
                        os.path.join(uploads, 'SampleSheet.csv'),
                        faciliteit=True)
        S.write_files(readlength=readlength)
        return redirect(url_for('uploaded_file',
                                filename='SampleSheet.csv'))

    return render_template('faciliteit.html')


@app.route('/createsamplesheet/created/<filename>')
def uploaded_file(filename):
    return render_template('download.html', filename=filename)


@app.route('/createsamplesheet/<path:filename>')
def download(filename):
    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    return send_from_directory(directory=uploads, filename=filename)


if __name__ == '__main__':
    app.run(debug=True)
