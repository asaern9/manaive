import base64
from .common import headers
from odoo import models, fields, api
import requests
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class MovieModel(models.Model):
    _name = "movie"
    _description = "Model to hold movie data"

    title = fields.Char(required=True)
    storyline = fields.Text()
    release_date = fields.Date()
    poster = fields.Image()
    runtime = fields.Float()
    imdb_rating = fields.Selection(
        [("0", "No rating"), ("1", "Very low"), ("2", "Low"), ("3", "Good"), ("4", "Very good"), ("5", "Excellent")],
        default=0, string="Imdb Rating")
    genre_ids = fields.Many2many(comodel_name="movie.genre")
    link_to_trailer = fields.Char(string="Homepage")
    original_language_id = fields.Many2one(comodel_name="res.lang")
    country_id = fields.Many2one(comodel_name="res.country")
    box_office = fields.Float()
    parental_guide = fields.Boolean(default=True, string="Adult")
    publisher_ids = fields.Many2many(comodel_name="res.partner", column1='movie_id', column2='partner_id',
                                     relation='movie_publisher_rel', string='Publishers')

    director_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                    relation="movie_director_rel", string="Directors")

    producer_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                    relation="movie_producer_rel", string="Producers")

    cast_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                relation="movie_cast_rel", string="Cast")

    writer_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                  relation="movie_writer_rel", string="Writers")

    editor_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                  relation="movie_editor_rel", string="Editors")

    music_partner_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                         relation="movie_music_personal_rel", string="Music by")

    story_partner_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                         relation="story_personal_rel", string="Story by")

    screenplay_partner_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                              relation="screenplay_personal_rel", string="Screenplay by")

    distributor_ids = fields.Many2many(comodel_name="res.partner", column1="movie_id", column2="partner_id",
                                       relation="movie_editor_rel", string="Distributors")
    movie_specific_id = fields.Integer(read_only=True)

    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)
    stage_id = fields.Many2one(comodel_name="movie.stage", group_expand='_read_group_stage_ids')

    @api.depends("title")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.title

    def _downlaod_image(self, poster_path):
        url = "http://image.tmdb.org/t/p/w500" + poster_path
        response = requests.get(url)
        if response.status_code != 200:
            raise UserError("Internet Connection Failed")
        return base64.b64encode(response.content)

    def _format_payload(self, movie):
        return {
            "title": movie['title'],
            "storyline": movie["overview"],
            "release_date": movie["release_date"],
            "original_language_id": self.env["res.lang"].search([("iso_code", "=", movie["original_language"])]).id,
            "poster": self._downlaod_image(movie["poster_path"]),
            "movie_specific_id": movie["id"],
            "stage_id": self.env["movie.stage"].search([("name", "=", "New")]).id
        }

    @api.model
    def fetch_and_save_movies(self, category):
        create_vals = []
        if category == "trending_movies":
            movies = self.fetch_trending_movies()
            for movie in movies["results"]:
                if not self.search([("title", "=", movie["title"])]):
                    create_vals.append(self._format_payload(movie))
        self.create(create_vals)

    @api.model
    def fetch_trending_movies(self):
        url = "https://api.themoviedb.org/3/trending/movie/day?language=en-US"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise UserError("Internet Connection Failed")
        return response.json()

    @api.depends("movie_specific_id")
    def update_movie(self):
        self.update_cast()
        self.update_other_details()

    @api.depends("movie_specific_id")
    def update_other_details(self):
        url = f"https://api.themoviedb.org/3/movie/{self.movie_specific_id}?language=en-US"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise UserError("Internet Connection Failed")
        data = response.json()
        self.update_genre(data["genres"])
        self.update_publisher(data["production_companies"])
        self.runtime = self._format_runtime(data["runtime"])
        self.parental_guide = data["adult"]
        self.link_to_trailer = data["homepage"]
        self.box_office = data["revenue"]

    def _format_runtime(self, runtime):
        runtime = str(runtime)
        return float(runtime[0] + "." + runtime[-2:])

    @api.depends("movie_specific_id")
    def update_publisher(self, publisher_list):
        for i in publisher_list:
            record = self.env["res.partner"].search([("name", "=", i["name"])]).id
            if record:
                self.write({"publisher_ids": [(4, record)]})
            else:
                self.write({"publisher_ids": [(0, 0, {"name": i["name"]})]})

    @api.depends("movie_specific_id")
    def update_genre(self, genre_list):
        for i in genre_list:
            record = self.env["movie.genre"].search([("name", "=", i["name"])]).id
            if record:
                self.write({"genre_ids": [(4, record)]})
            else:
                self.write({"genre_ids": [(0, 0, {"name": i["name"]})]})

    @api.depends("movie_specific_id")
    def update_cast(self):
        url = f"https://api.themoviedb.org/3/movie/{self.movie_specific_id}/credits?language=en-US"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise UserError("Internet Connection Failed")
        data = response.json()
        cast_from_movie_id = data["cast"]
        crew_from_movie_id = data["crew"]
        for i in cast_from_movie_id:
            record_id = self.env["res.partner"].search([("name", "=", i["name"])]).id
            if record_id:
                self.write({"cast_ids": [(4, record_id)]})
            else:
                self.write({"cast_ids": [(0, 0, {"name": i["name"]})]})

        for i in crew_from_movie_id:
            record_id = self.env["res.partner"].search([("name", "=", i["name"])]).id
            if record_id:
                if i["known_for_department"] == "Production":
                    self.write({"producer_ids": [(4, record_id)]})
                elif i["known_for_department"] == "Sound":
                    self.write({"music_partner_ids": [(4, record_id)]})
                elif i["known_for_department"] == "Directing":
                    self.write({"director_ids": [(4, record_id)]})
                elif i["known_for_department"] == "Writing":
                    self.write({"writer_ids": [(4, record_id)]})
                elif i["known_for_department"] == "Editing":
                    self.write({"editor_ids": [(4, record_id)]})
                else:
                    continue
            else:
                if i["known_for_department"] == "Production":
                    self.write({"producer_ids": [(0, 0, {"name": i["name"]})]})
                elif i["known_for_department"] == "Sound":
                    self.write({"music_partner_ids": [(0, 0, {"name": i["name"]})]})
                elif i["known_for_department"] == "Directing":
                    self.write({"director_ids": [(0, 0, {"name": i["name"]})]})
                elif i["known_for_department"] == "Writing":
                    self.write({"writer_ids": [(0, 0, {"name": i["name"]})]})
                elif i["known_for_department"] == "Editing":
                    self.write({"editor_ids": [(0, 0, {"name": i["name"]})]})
                else:
                    continue

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return self.env['movie.stage'].search([], order=order)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        search_name = ""
        if len(args) != 0:
            search_name = args[0][2]
        movie = super(MovieModel, self).search(args, offset=offset, limit=limit, order=order, count=count)
        if len(movie) == 0:
            self.search_movie(search_name)
        return movie

    def search_movie(self, movie_title):
        print("We have movie to fetch", movie_title)
        url = f"https://api.themoviedb.org/3/search/movie?query={movie_title}&include_adult=false&language=en-US&page=1"
        response = requests.get(url, headers=headers)
        print(response.json())
