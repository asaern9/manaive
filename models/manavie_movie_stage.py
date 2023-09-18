from odoo import models
from odoo import fields
from datetime import datetime, timedelta


class StageModel(models.Model):
    _name = "movie.stage"
    _description = "Model to hold stage data"

    name = fields.Char(unique=True)

