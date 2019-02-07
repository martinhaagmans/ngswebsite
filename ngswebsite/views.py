import os
import sys
import json
import logging
import sqlite3
import subprocess

from pathlib import Path
from logging import handlers

from flask import Flask
from flask import render_template
from flask import redirect
from flask import url_for
from flask import jsonify
from flask import request
from flask import make_response

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'uploads'

HOME = '/data/dnadiag'

NGSLIBLOC = os.path.join(HOME, 'ngsscriptlibrary')
sys.path.insert(0, NGSLIBLOC)

DB_TARGETS= os.path.join(HOME, 'ngstargets')
DB_GENESIS = os.path.join(DB_TARGETS, 'varia', 'captures.sqlite')
DB_METRICS = os.path.join(HOME, 'ngswebsite', 'ngswebsite', 'data', 'metrics.sqlite')
DB_SAMPLESHEET = os.path.join(HOME, 'ngswebsite', 'ngswebsite', 'data', 'samplesheets.sqlite')

from ngsscriptlibrary import TargetDatabase
from ngsscriptlibrary import SampleSheet

basedir = os.path.dirname(os.path.realpath(__file__))
log = os.path.join(basedir, 'samplesheets.log')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh = handlers.RotatingFileHandler(log, maxBytes=10*1024*1024, backupCount=5)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

def get_snpcheck_dict():
    d = {1: {'rsid' : 'rs3729547', 'locus' : 'chr1:201334382', 'SNP': 'G/A'},
         2: {'rsid' : 'rs12920', 'locus' : 'chr2:220285666', 'SNP': 'G/C'},
         3: {'rsid' : 'rs4685076', 'locus' : 'chr3:14174427', 'SNP': 'A/T'},
         4: {'rsid' : 'rs1805126', 'locus' : 'chr3:38592406', 'SNP': 'A/G'},
         5: {'rsid' : 'rs2250736', 'locus' : 'chr3:53700550', 'SNP': 'T/C'},
         6: {'rsid' : 'rs1801193', 'locus' : 'chr5:155771579', 'SNP': 'T/C'},
         7: {'rsid' : 'rs2744380', 'locus' : 'chr6:7585967', 'SNP': 'G/C'},
         8: {'rsid' : 'rs1063243', 'locus' : 'chr7:91726927', 'SNP': 'A/C'},
         9: {'rsid' : 'rs4485000', 'locus' : 'chr10:18789724', 'SNP': 'T/G'},
         10: {'rsid' : 'rs767809', 'locus' : 'chr10:75865065', 'SNP': 'G/A'},
         11: {'rsid' : 'rs3759236', 'locus' : 'chr12:22068849', 'SNP': 'G/T'},
         12: {'rsid' : 'rs1071646', 'locus' : 'chr15:63351840', 'SNP': 'C/A'}
        }
    return d

def get_gpos2snp_lookup():
    d = {'chr1:201334382': 1,
         'chr10:75865065': 10,
         'chr12:22068849': 11,
         'chr3:14174427': 3,
         'chr5:155771579': 6,
         'chr2:220285666': 2,
         'chr3:38592406': 4,
         'chr3:53700550': 5,
         'chr6:7585967': 7,
         'chr15:63351840': 12,
         'chr10:18789724': 9,
         'chr7:91726927': 8}
    return d

def check_serie_is_number(serie, max_serie=5000):
    """Check if serie is valid and return boolean.
    
    Check if serie is a integer and if so if it is not
    a made up number for research. First check if it can 
    be converted to a integer and if so check if it has a 
    smaller value than max_serie. Sometimes a serie
    gets a follow letter (e.g. 400B, 400C) so perform the 
    same checks minus the last character in serie.
    """
    is_number = True
    try:
        int(serie)
    except ValueError:
        is_number = False
    else:
        is_number = int(serie) < max_serie
    try:
        int(serie[:-1])
    except ValueError:
        is_number = False
    else:
        is_number = int(serie[:-1]) < max_serie        
    return is_number

def count_values_in_list(list_to_count):
    counts = list()
    
    for value in set(sorted(list_to_count)):
        value_count = value, list_to_count.count(value)
        counts.append(value_count)

    return counts

def generate(path):
    with open(path) as f:
        yield from f
    os.remove(path)

def download_genelist(todo_list, d, genesis):
    pakket = todo_list['pakket']
    panel = todo_list['panel']
    genes = d['pakketten'][pakket][0][1]
    out = list()
    if panel is not None:
        agenes = d['panels'][panel][0][1]
        cd = 'attachment; filename={}.{}.{}.csv'.format(genesis, pakket,
                                                        panel)
        for gene in genes:
            if gene in agenes:
                out.append('{},A'.format(gene))
            elif gene not in agenes:
                out.append('{},C'.format(gene))
    elif panel is None:
        cd = 'attachment; filename={}.{}.csv'.format(genesis, pakket)
        for gene in genes:
            out.append('{},A'.format(gene))
    r = make_response('\n'.join(out))
    r.headers['Content-Disposition'] = cd
    r.mimetype = 'text/csv'
    return r

def download_target(targetname, targetsoort):
    out = list()
    target = os.path.join(DB_TARGETS, targetsoort,
                          '{}_target.bed'.format(targetname))
    with open(target, 'r') as f:
        for line in f:
            out.append(line.strip())

    cd = 'attachment; filename={}_target.bed'.format(targetname)
    r = make_response('\n'.join(out))
    r.headers['Content-Disposition'] = cd
    r.mimetype = 'text/csv'
    return r

@app.route('/snpcheck')
def snpcheck():
    conn = sqlite3.connect(DB_METRICS)
    c = conn.cursor()
    c.execute('SELECT * from snpcheck')
    
    nr_samples = 0

    loci = list()
    series = list()
    taqman_nodata = list()
    taqman_unknown = list()
    taqman_negative = list()
    taqman_unknown_counts = dict()
    taqman_negative_counts = dict()
    

    for _ in c.fetchall():
        sample, serie, data = _

        try:
            int(serie)
        except ValueError:
            continue

        nr_samples += 1
        
        if not serie in series:
            series.append(serie)

        data = json.loads(data)
        taqman_nodata_count = 0

        for locus, call in data['COMP'].items():
            if call.lower() == 'unknown':
                taqman_unknown.append(locus)
            elif call.lower() == 'negative':
                taqman_negative.append(locus)
            elif call.lower() == 'notaqman':
                taqman_nodata_count += 1

            if locus not in loci:
                loci.append(locus)

        if taqman_nodata_count == len(data['ALT'].keys()):
            taqman_nodata.append(sample)

    loci.sort()
    series.sort()
    taqman_nodata.sort()
    taqman_unknown.sort()
    taqman_negative.sort()

    for locus in loci:
        if locus in taqman_unknown:
            taqman_unknown_counts[locus] = taqman_unknown.count(locus)
        else:
            taqman_unknown_counts[locus] = 0

        if locus in taqman_negative:
            taqman_negative_counts[locus] = taqman_negative.count(locus)       
        else:
            taqman_negative_counts[locus] = 0
        
    return render_template('showData_snpcheck.html', title="TaqMan SNP check",
                            loci=loci, 
                            series=len(series),
                            gpos2snp=get_gpos2snp_lookup(),
                            snpcheckd=get_snpcheck_dict(),
                            nr_samples=nr_samples,
                            nr_samples_notaqman=len(taqman_nodata),                            
                            taqman_unknown_counts=taqman_unknown_counts,
                            taqman_negative_counts=taqman_negative_counts
                            )


@app.route('/picardmetrics')
def picardmetrics():
    return render_template('showData_picardmetrics.html', title='Picard metrics')


@app.route('/_picardmetrics')
def _picardmetrics():
    conn = sqlite3.connect(DB_METRICS)
    c = conn.cursor()
    c.execute('''SELECT h.SAMPLE, h.SERIE, h.BAIT_SET, h.TOTAL_READS,
                 h.PCT_PF_UQ_READS, h.PCT_SELECTED_BASES, 
                 h.MEAN_TARGET_COVERAGE, h.AT_DROPOUT, h.GC_DROPOUT,
                 i.MEAN_INSERT_SIZE, i.STANDARD_DEVIATION 
                 FROM hsmetrics h
                 INNER JOIN insertsize i
                 ON (h.SAMPLE = i.SAMPLE
                 AND h.SERIE = i.SERIE)''')

    data = list()

    for _ in c.fetchall():
        sample, serie, target, tr, uqr, ot, mean, at, gc, imean, std = _

        if not check_serie_is_number(serie):
            continue
            
        __ = dict()
        __['sample'] = sample
        __['serie'] = serie
        __['target'] = target
        __['total_reads'] = int(tr)
        __['unique_reads'] = int(uqr*100)
        __['ontarget'] = int(ot*100)
        __['mean'] = int(mean)
        __['at_dropout'] = round(float(at), 2)
        __['gc_dropout'] = round(float(gc), 2)
        __['insert_mean'] = round(float(imean), 0)
        __['insert_std'] = round(float(std), 0)
        data.append(__)
    
    return jsonify(data=data)

@app.route('/callables')
def callables():
    return render_template('showData_callables.html', title='Callable loci')


@app.route('/_callables')
def _callables():
    conn = sqlite3.connect(DB_METRICS)
    c = conn.cursor()
    c.execute('''SELECT c.SAMPLE, c.SERIE, c.TARGET, 
                 c.CALLABLE, c.NO_COVERAGE, c.LOW_COVERAGE, 
                 c.POOR_MAPPING_QUALITY, s.DATA
                 FROM callable c
                 INNER JOIN sangers s 
                 ON (c.SAMPLE = s.SAMPLE
                 AND c.SERIE = s.SERIE 
                 AND c.TARGET = s.TARGET)
                 ''')

    data = list()

    for _ in c.fetchall():
        sample, serie, target, c, nc, lc, pm, sanger_data = _

        if not check_serie_is_number(serie):
            continue

        total = int(c) + int(nc) + int(lc) + int(pm)

        sanger_data = json.loads(sanger_data)

        if 'Geen sangers' in sanger_data:
            nr_sangers = 0
        else:
            nr_sangers = len(sanger_data)

        __ = dict()
        __['sample'] = sample
        __['serie'] = serie
        __['target'] = target
        __['callable'] = int(c)
        __['nocoverage'] = int(nc)
        __['lowcoverage'] = int(lc)
        __['poormapping'] = int(pm)
        __['perc_callable'] = round((100 * (c / total)), 2)
        __['nr_sangers'] = nr_sangers
   
        data.append(__)
    
    return jsonify(data=data)


@app.route('/diagnostiek/')
def genesis():
    conn = sqlite3.connect(DB_SAMPLESHEET)
    c = conn.cursor()
    c.execute('''SELECT SAMPLE, SERIE, genesis
                 FROM todo''')

    T = TargetDatabase(DB_GENESIS)
    all_genesis_codes = T.get_all_tests()
    all_genesis_done = list()
    all_series = list()

    for _ in c.fetchall():

        _sample, serie, genesis = _

        if not check_serie_is_number(serie):
            continue

        all_genesis_done.append(genesis)

        if serie not in all_series:
            all_series.append(serie)

    data = list()
    
    all_genesis_done.sort()

    all_genesis_codes = sorted(all_genesis_codes)
    
    for g in all_genesis_codes:
        d = T.get_info_for_genesis(g)
        capture = d['capture']
        pakket = d['pakket']
        panel = d['panel']
        aandoening = d['aandoening']
        aantal = all_genesis_done.count(g)

        data.append((g, aantal, capture, pakket, panel, aandoening))        
        
    return render_template('showData_allGenesis.html', 
                            title='Verwerkte samples',
                            data=data, 
                            series=len(all_series),
                            samples=len(all_genesis_done))


@app.route('/diagnostiek/<genesis>', methods=['GET', 'POST'])
def show_genesis(genesis):
    T = TargetDatabase(DB_GENESIS)

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

    if request.method == 'POST':
        if 'genes' in request.form:
            return download_genelist(todo_list, d, genesis)
        else:
            data = request.form.to_dict()
            targetname, targetsoort = list(data.keys())[0].split(':')
            return download_target(targetname, targetsoort)
            
    return render_template('show_Genesis.html', 
                            info=d, todo=todo_list,
                            title=todo_list['aandoening'])


@app.route('/createsamplesheet/', methods=['GET', 'POST'])
@app.route('/create-samplesheet/', methods=['GET', 'POST'])
def create_samplesheet():
    if request.method == 'POST':
        serie = request.form['serie']
        analist = request.form['analist']
        analist = analist.replace(' ', '_')
        nullijst_todo = request.form['samples']
        logger.info('Start maken samplesheet voor MS{} op verzoek {}'.format(serie, analist))
        uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
        with open(os.path.join(uploads, 'samplesheet.tmp'), 'w') as f, open(os.path.join(uploads, 'MS{}_sample_info.txt'.format(serie)), 'w') as f_cnv:
            for line in nullijst_todo.split('\n'):
                if line:
                    logger.info(json.dumps(line))
                    line = line.replace(' ', '-')
                    dnr, bc, test, cnvarchive = line.split()
                    f.write('{}\t{}\t{}\n'.format(dnr, test, bc))

                    robot = cnvarchive.lower() == 'robot'
                    hand = cnvarchive.lower() == 'hand'
                    flexstar = cnvarchive.lower() == 'flexstar'

                    if not robot and not hand and not flexstar:
                        f_cnv.write('{}\t{}\t{}\n'.format(serie, dnr, cnvarchive))

        S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'),
                        serie,
                        os.path.join(uploads, 'MS{}.csv'.format(serie)))
        S.write_files(analist=analist)
        logger.info('Einde maken samplesheet voor MS{} op verzoek {}'.format(serie, analist))

        subprocess.call(["cp", os.path.join(uploads, 'MS{}_sample_info.txt'.format(serie)),
                          "/data/dnadiag/databases/materiaalsoort"])
        return redirect(url_for('uploaded_file',
                                 filename='MS{}.csv'.format(serie)))


    return render_template('create_samplesheet.html', 
                            title="Maak een samplesheet")


@app.route('/_genesiscodes/')
@app.route('/create-samplesheet/_genesiscodes/')
def _get_genesiscodes():
    conn = sqlite3.connect(DB_GENESIS)
    c = conn.cursor()
    c.execute('''SELECT genesis FROM genesis''')
    genesis_codes = [val for tup in c.fetchall() for val in tup]
    return jsonify(data=genesis_codes)

@app.route('/createsamplesheet/<path:filename>')
def download(filename):
    file_path = os.path.join(os.path.join(app.root_path,
                                          app.config['UPLOAD_FOLDER'],
                                          filename))
    r = app.response_class(generate(file_path), mimetype='text/csv')
    r.headers.set('Content-Disposition', 'attachment', filename=filename)
    return r

@app.route('/create-samplesheet/created/<filename>')
def uploaded_file(filename):
    return render_template('download.html', filename=filename)

@app.route('/')
def intro():
    return render_template('explanation_general.html')

@app.route('/uitleg/database/')
def database_explained():
    return render_template('explanation_database.html')

@app.route('/uitleg/pipeline/')
def pipeline_explained():
    return render_template('explanation_pipeline.html')

@app.route('/uitleg/naamgeving/')
def nomenclature_explained():
    return render_template('explanation_nomenclature.html')

@app.route('/uitleg/samplesheet/')
def samplesheet_explained():
    return render_template('explanation_samplesheet.html')

@app.route('/uitleg/pipeline/snv')
def std_pipe():
    return render_template('explanation_pipeline_vars.html')

@app.route('/uitleg/pipeline/cnv')
def cnv_pipe():
    return render_template('explanation_pipeline_cnv.html')

@app.route('/uitleg/pipeline/mosa')
def mosaic_pipe():
    return render_template('explanation_pipeline_mosa.html')

@app.route('/uitleg/pipeline/qc')
def qc_pipe():
    return render_template('explanation_pipeline_qc.html')

@app.route('/howto/pipeline')
def howto_pipe():
    return render_template('howto_pipeline.html', title='Pipeline runnen')    
