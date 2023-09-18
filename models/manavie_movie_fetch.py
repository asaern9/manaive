from odoo import models, fields
from datetime import datetime, timedelta


class FetchModel(models.TransientModel):
    _name = "movie.fetch"
    # _inherit = 'movie'
    _description = "Model to hold website data"

    movie_category = fields.Selection([("trending_movies", "Trending Movies")], string="Select")

    def fetch_movie_main(self):
        self.env["movie"].fetch_and_save_movies(category=self.movie_category)

