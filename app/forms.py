from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Length


class NewTestForm(FlaskForm):
    genesis = StringField('genesis', validators=[Length(min=2, max=10), DataRequired()])
    aandoening = StringField('aandoening', validators=[DataRequired()])
    capture = StringField('capture', validators=[DataRequired()])
    pakket = StringField('pakket')
    panel = StringField('panel')
    oid = StringField('oid', validators=[DataRequired()])
    lotnummer = IntegerField('lotnummer', validators=[DataRequired()])
    actief = BooleanField('actief', default=False)
    verdund = BooleanField('verdund', default=False)
    cnvdetectie = BooleanField('cnvdetectie', default=True)
    printcnv = BooleanField('printcnv', default=False)
    mozaiekdetectie = BooleanField('mozaiekdetectie', default=False)
    capturetarget = FileField()
    capturegenen = FileField()
    pakkettarget = FileField()
    pakketgenen = FileField()
    paneltarget = FileField()
    panelgenen = FileField()

class NewLotForm(FlaskForm):
    lotnummer = StringField('lotnummer', validators=[DataRequired()])
