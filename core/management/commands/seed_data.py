"""
Populate the site with realistic starter content.

Idempotent: safe to run repeatedly. Pass --flush-content to rebuild the
demo content from scratch (never touches users or enquiries).
"""
import io
import random

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from academics.models import (
    Course,
    Department,
    Facility,
    IndustryPartner,
    Program,
    School,
)
from admissions.models import AdmissionStep, City, Enquiry, Scholarship, State
from core.models import (
    FAQ,
    Centre,
    ChancellorMessage,
    Enlistment,
    FooterLink,
    HeroSlide,
    MenuItem,
    Offering,
    Page,
    QuickLink,
    SiteConfiguration,
    SocialLink,
    Testimonial,
    VideoFeature,
)
from events.models import Event, Notice

GOLD = (233, 207, 82)
DARK = (43, 43, 43)


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def _font(size):
    from PIL import ImageFont

    for candidate in ("arialbd.ttf", "arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_center(draw, box, text, font, fill):
    """Draw multi-line text centred inside (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    lines = text.split("\n")
    try:
        line_h = font.getbbox("Ag")[3] + 10
    except AttributeError:                       # pragma: no cover - old Pillow
        line_h = font.getsize("Ag")[1] + 10
    total = line_h * len(lines)
    y = y0 + (y1 - y0 - total) / 2
    for line in lines:
        try:
            width = draw.textlength(line, font=font)
        except AttributeError:                   # pragma: no cover
            width = font.getsize(line)[0]
        draw.text((x0 + (x1 - x0 - width) / 2, y), line, font=font, fill=fill)
        y += line_h


def make_banner(text, size=(1600, 650), bg=(28, 42, 66), accent=GOLD, subtitle=""):
    """A hero-slide style image: diagonal accent block + headline."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = size

    draw.polygon([(w * 0.42, h), (w, 0), (w, h)], fill=accent + (255,))
    draw.polygon([(0, 0), (w * 0.55, 0), (0, h)], fill=(255, 255, 255, 22))
    for i in range(14):
        x = int(w * 0.55) + i * 42
        draw.rectangle([x, h - random.randint(90, 260), x + 26, h], fill=(0, 0, 0, 55))

    _text_center(draw, (60, 60, int(w * 0.52), h - 60), text, _font(58), (255, 255, 255))
    if subtitle:
        _text_center(draw, (60, h - 170, int(w * 0.52), h - 70), subtitle, _font(28), (235, 235, 235))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


def make_card(text, size=(700, 400), bg=(31, 107, 92)):
    """Chalkboard-style school card."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = size
    rng = random.Random(hash(text) & 0xFFFF)
    for _ in range(40):
        x, y = rng.randrange(w), rng.randrange(h)
        draw.ellipse([x, y, x + rng.randrange(6, 30), y + rng.randrange(6, 30)],
                     outline=(255, 255, 255, 26), width=2)
    draw.rectangle([14, 14, w - 14, h - 14], outline=(255, 255, 255, 40), width=2)
    _text_center(draw, (40, 40, w - 40, h - 40), text, _font(30), (255, 255, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=84, optimize=True)
    return buffer.getvalue()


def make_photo(text, size=(600, 450), bg=(212, 205, 186)):
    """Event/news photo stand-in."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = size
    rng = random.Random(hash(text) & 0xFFFF)
    draw.rectangle([0, int(h * 0.72), w, h], fill=(184, 176, 152))
    for i in range(rng.randrange(5, 9)):
        cx = 60 + i * (w - 120) / 6
        draw.ellipse([cx - 22, h * 0.42, cx + 22, h * 0.42 + 44], fill=(90, 80, 70))
        draw.rectangle([cx - 26, h * 0.5, cx + 26, h * 0.76],
                       fill=(rng.randrange(40, 200), rng.randrange(40, 160), rng.randrange(40, 160)))
    _text_center(draw, (30, h - 96, w - 30, h - 20), text, _font(22), (60, 55, 42))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82, optimize=True)
    return buffer.getvalue()


def make_logo(text, size=(400, 260), bg=(238, 238, 238), fg=(30, 60, 130)):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)
    _text_center(draw, (20, 20, size[0] - 20, size[1] - 20), text, _font(52), fg)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def make_portrait(name, size=(300, 300)):
    from PIL import Image, ImageDraw

    rng = random.Random(hash(name) & 0xFFFF)
    bg = (rng.randrange(120, 200), rng.randrange(120, 200), rng.randrange(130, 205))
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.ellipse([w * .3, h * .18, w * .7, h * .58], fill=(226, 196, 168))
    draw.ellipse([w * .12, h * .58, w * .88, h * 1.35], fill=(60, 70, 96))
    initials = "".join(p[0] for p in name.split()[:2]).upper()
    _text_center(draw, (0, h - 70, w, h - 10), initials, _font(30), (255, 255, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def attach(instance, field, filename, payload):
    """
    Attach generated bytes to an ImageField unless a real file is already there.

    The storage check matters on hosts with an ephemeral filesystem (Render's
    free tier): the database row survives a redeploy but the file does not, so
    a field that merely *looks* populated would render as a broken image.
    """
    field_file = getattr(instance, field)
    if field_file:
        try:
            if field_file.storage.exists(field_file.name):
                return
        except (NotImplementedError, OSError):
            return          # remote storage that cannot be probed — leave it be
    field_file.save(filename, ContentFile(payload), save=True)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
SCHOOLS = [
    ("School of Engineering", "Computer science, electronics, civil, mechanical and AI-integrated engineering programmes.", (26, 74, 110)),
    ("School of Management & Commerce", "BBA, MBA, B.Com and economics programmes with industry immersion.", (110, 62, 26)),
    ("School of Law", "Five-year integrated and three-year LL.B programmes, CLAT enlisted.", (70, 40, 96)),
    ("School of Arts, Media & Design", "Journalism, mass communication, animation, fine arts and design.", (31, 107, 92)),
    ("School of Nursing, Health & Pharmaceutical Sciences", "Nursing, pharmacy, optometry and allied health sciences.", (24, 96, 84)),
    ("School of Science & Technology", "Physics, chemistry, mathematics, statistics and data science.", (36, 82, 118)),
    ("School of Life, Agricultural & Biotechnological Sciences", "Biotechnology, microbiology, bioinformatics and agriculture.", (46, 100, 46)),
    ("School of Humanities, Languages and Social Sciences", "English, history, political science, sociology and psychology.", (120, 56, 60)),
    ("School of Lifelong Learning", "Skill-development, certificate and continuing-education programmes.", (92, 74, 30)),
]

COURSES = [
    # (school index, programme, name, duration)
    (0, "UG", "B.Tech in Computer Science & Engineering", "4 Years / 8 Semesters"),
    (0, "UG", "B.Tech in Computer Science & Engineering (AI & ML)", "4 Years / 8 Semesters"),
    (0, "UG", "B.Tech in Electronics & Communication Engineering", "4 Years / 8 Semesters"),
    (0, "UG", "B.Tech in Civil Engineering", "4 Years / 8 Semesters"),
    (0, "UG", "B.Tech in Mechanical Engineering", "4 Years / 8 Semesters"),
    (0, "PG", "M.Tech in Computer Science & Engineering", "2 Years / 4 Semesters"),
    (0, "PhD", "Ph.D in Engineering & Technology", "3-6 Years"),
    (1, "UG", "BBA (Honours with Research)", "3-4 Years"),
    (1, "UG", "B.Com (Honours with Research)", "3-4 Years"),
    (1, "PG", "MBA", "2 Years / 4 Semesters"),
    (1, "PG", "M.Com", "2 Years / 4 Semesters"),
    (1, "PhD", "Ph.D in Management", "3-6 Years"),
    (2, "UG", "B.A. LL.B (Hons.)", "5 Years / 10 Semesters"),
    (2, "UG", "BBA LL.B (Hons.)", "5 Years / 10 Semesters"),
    (2, "PG", "LL.M", "1 Year / 2 Semesters"),
    (3, "UG", "B.A. in Journalism & Mass Communication", "3-4 Years"),
    (3, "UG", "B.Des in Fashion Design", "4 Years / 8 Semesters"),
    (3, "UG", "B.Des in Animation & Graphics", "4 Years / 8 Semesters"),
    (3, "PG", "M.A. in Journalism & Mass Communication", "2 Years / 4 Semesters"),
    (4, "UG", "B.Sc in Nursing", "4 Years / 8 Semesters"),
    (4, "UG", "B.Pharm", "4 Years / 8 Semesters"),
    (4, "UG", "B.Optom (Optometry)", "4 Years"),
    (4, "PG", "M.Pharm", "2 Years / 4 Semesters"),
    (5, "UG", "B.Sc in Physics (Honours with Research)", "3-4 Years"),
    (5, "UG", "B.Sc in Statistics & Data Science", "3-4 Years"),
    (5, "PG", "M.Sc in Mathematics & Computing", "2 Years / 4 Semesters"),
    (6, "UG", "B.Sc in Biotechnology", "3-4 Years"),
    (6, "UG", "B.Sc in Microbiology", "3-4 Years"),
    (6, "PG", "M.Sc in Bioinformatics", "2 Years / 4 Semesters"),
    (7, "UG", "B.A. in English (Honours with Research)", "3-4 Years"),
    (7, "UG", "B.A. in Psychology", "3-4 Years"),
    (7, "PG", "M.A. in Sociology", "2 Years / 4 Semesters"),
    (8, "Diploma", "Diploma in Hospitality & Tourism Administration", "1 Year"),
]

STATES = {
    "West Bengal": ["Kolkata", "Howrah", "Siliguri", "Durgapur", "Asansol", "Barasat", "Kharagpur"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Puri"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat"],
    "Delhi": ["New Delhi", "Dwarka", "Rohini"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Varanasi", "Noida", "Ghaziabad"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai"],
    "Tripura": ["Agartala", "Udaipur"],
    "Sikkim": ["Gangtok", "Namchi"],
    "Meghalaya": ["Shillong", "Tura"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode"],
    "Telangana": ["Hyderabad", "Warangal"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur"],
    "Punjab": ["Ludhiana", "Amritsar", "Chandigarh"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat"],
}

MENU = [
    ("About SVU", "/page/about-svu/", [
        ("Overview", "/page/about-svu/"),
        ("Chancellor's Message", "/page/chancellors-message/"),
        ("Vision & Mission", "/page/vision-mission/"),
        ("Statutory Bodies", "/page/statutory-bodies/"),
        ("UGC Compliance Documents", "/page/ugc-compliance/"),
        ("Public Self-Disclosure", "/page/public-self-disclosure/"),
    ]),
    ("Academics", "/academics/schools/", [
        ("SVU Schools", "/academics/schools/"),
        ("Schools & Courses", "/academics/courses/"),
        ("Academic Calendar", "/page/academic-calendar/"),
        ("Library", "/page/library/"),
    ]),
    ("Admission", "/admission/", [
        ("Admission Process", "/admission/"),
        ("Apply Online", "/admission/apply/"),
        ("Scholarships", "/page/scholarships/"),
        ("Fee Refund Policy", "/page/fee-refund-policy/"),
    ]),
    ("Campus Life", "/academics/facilities/", [
        ("SVU Facilities", "/academics/facilities/"),
        ("Hostel", "/page/hostel/"),
        ("Sports", "/page/sports/"),
        ("Clubs & Societies", "/page/clubs-societies/"),
    ]),
    ("Events", "/events/", []),
    ("IQAC", "/page/iqac/", [
        ("About IQAC", "/page/iqac/"),
        ("AQAR Reports", "/page/aqar-reports/"),
        ("Feedback", "/page/iqac-feedback/"),
    ]),
    ("Student Form", "/page/student-forms/", []),
    ("NIRF", "/page/nirf/", [
        ("NIRF 2026", "/page/nirf/"),
        ("Data Templates", "/page/nirf-data/"),
    ]),
    ("Centre", "/page/centre-of-excellence/", [
        ("Centre for Innovation & Entrepreneurship", "/page/centre-innovation/"),
        ("Centre of Excellence", "/page/centre-of-excellence/"),
        ("Centre for Women Studies", "/page/centre-women-studies/"),
        ("Industry Collaboration", "/academics/industry-partners/"),
    ]),
    ("WILP", "/page/wilp/", []),
    ("Student Welfare Committees", "/page/student-welfare/", [
        ("Anti-Ragging Committee", "/page/anti-ragging/"),
        ("Internal Complaints Committee", "/page/internal-complaints/"),
        ("Grievance Redressal", "/page/grievance-redressal/"),
        ("SC/ST Committee", "/page/sc-st-committee/"),
    ]),
    ("Examination", "/page/examination/", [
        ("Examination Notice", "/page/examination/"),
        ("Results", "/page/results/"),
        ("Question Papers", "/page/question-papers/"),
    ]),
]


class Command(BaseCommand):
    help = "Seed the database with realistic starter content for the SVU website."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush-content",
            action="store_true",
            help="Delete existing demo content first (never touches users or enquiries).",
        )
        parser.add_argument(
            "--only-if-empty",
            action="store_true",
            help=("Seed only when the site has no schools yet. Use this on deploy "
                  "so a redeploy never resurrects demo rows an editor deleted."),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["only_if_empty"] and School.objects.exists():
            self.stdout.write(
                "Content already present — skipping seed (--only-if-empty)."
            )
            # Still repair imagery lost to an ephemeral filesystem. Every
            # section that owns a generated file has to be listed here.
            self._site_config()
            self._slides()
            self._enlistments()
            self._schools()
            self._chancellor()
            self._testimonials()
            self._events()
            self._facilities_partners()
            self.stdout.write(self.style.SUCCESS("Verified/restored generated imagery."))
            return

        if options["flush_content"]:
            self.stdout.write("Flushing existing demo content…")
            for model in (HeroSlide, QuickLink, Offering, Enlistment, VideoFeature,
                          Centre, Testimonial, FooterLink, MenuItem, SocialLink,
                          Notice, Event, Course, Department, School, Program,
                          Facility, IndustryPartner, AdmissionStep, Scholarship,
                          FAQ, Page, ChancellorMessage):
                if model is Course or not Enquiry.objects.exists():
                    model.objects.all().delete()

        self.stdout.write("Seeding…")
        config = self._site_config()
        self._social()
        self._menus()
        self._slides()
        self._quick_links()
        self._offerings()
        self._enlistments()
        programs = self._programs()
        schools = self._schools()
        self._courses(schools, programs)
        self._videos()
        self._chancellor()
        self._centres()
        self._testimonials()
        self._footer_links()
        self._notices()
        self._events()
        self._geography()
        self._pages()
        self._faqs()
        self._admission_extras()
        self._facilities_partners()

        self.stdout.write(self.style.SUCCESS(
            "\nSeeding complete.\n"
            f"  Schools : {School.objects.count()}\n"
            f"  Courses : {Course.objects.count()}\n"
            f"  Events  : {Event.objects.count()}\n"
            f"  Notices : {Notice.objects.count()}\n"
            f"  States  : {State.objects.count()} / Cities: {City.objects.count()}\n"
            f"  Pages   : {Page.objects.count()}\n"
        ))
        self.stdout.write("Next: python manage.py createsuperuser")

    # -- sections ----------------------------------------------------------
    def _site_config(self):
        config = SiteConfiguration.get_solo()
        # PLACEHOLDER COPY — replace in admin › Site configuration. The
        # establishment details (Act and year) are deliberately left out rather
        # than guessed; fill them in from the University's own records.
        config.welcome_text = (
            "Swami Vivekananda University (SVU) is a state private university built "
            "on the ideals and teachings of Swami Vivekananda. The university offers "
            "educational programmes and research in a wide array of subjects, under "
            "disciplines like Engineering and Technology, Science, Medicine, "
            "Management, Law, Humanities, Language and Literature, Pharmacy, "
            "Architecture, Social Sciences, Performing Arts, Sports, Media, Design, "
            "etc. Moreover, some unique courses will be introduced with the emphasis "
            "on skill development, entrepreneurship and women empowerment."
        )
        config.save()
        attach(config, "admission_ad_image", "admission-ad.jpg",
               make_banner("Swami Vivekananda\nUniversity\nExcellence in Education",
                           size=(450, 700), bg=(150, 90, 60),
                           subtitle="ADMISSIONS OPEN 2026-27"))
        return config

    def _social(self):
        for order, (platform, url) in enumerate([
            ("facebook", "https://www.facebook.com/svu"),
            ("twitter", "https://twitter.com/svu"),
            ("youtube", "https://www.youtube.com/@sisterniveditauniversity"),
            ("instagram", "https://www.instagram.com/svu"),
            ("linkedin", "https://www.linkedin.com/school/swami-vivekananda-university"),
        ]):
            SocialLink.objects.get_or_create(
                platform=platform, defaults={"url": url, "order": order}
            )

    def _menus(self):
        for order, (title, url) in enumerate([("FAQ", "/faq/"), ("Help Desk", "/contact/")]):
            MenuItem.objects.get_or_create(
                title=title, location=MenuItem.LOCATION_TOP,
                defaults={"url": url, "order": order},
            )

        for order, (title, url, children) in enumerate(MENU):
            parent, _ = MenuItem.objects.get_or_create(
                title=title, location=MenuItem.LOCATION_MAIN, parent=None,
                defaults={"url": url, "order": order},
            )
            for child_order, (child_title, child_url) in enumerate(children):
                MenuItem.objects.get_or_create(
                    title=child_title, parent=parent, location=MenuItem.LOCATION_MAIN,
                    defaults={"url": child_url, "order": child_order},
                )

    def _slides(self):
        slides = [
            ("For the first time in China, the Department of Computer Science "
             "at Swami Vivekananda University proudly marks its presence",
             "An international exposure programme for our students",
             (198, 122, 30)),
            ("Upto 100% Merit Scholarship",
             "51 LPA highest placement package — Admissions open 2026-27",
             (34, 34, 34)),
            ("Admission Open 2026-27",
             "UG, PG and Ph.D programmes | Call the admission helpline",
             (26, 74, 110)),
        ]
        for order, (title, subtitle, bg) in enumerate(slides):
            slide, created = HeroSlide.objects.get_or_create(
                title=title,
                defaults={
                    "subtitle": subtitle,
                    "alt_text": title[:150],
                    "order": order,
                    "link_url": "/admission/apply/",
                    "link_label": "Apply Now",
                },
            )
            attach(slide, "image", f"slide-{order + 1}.jpg",
                       make_banner(title[:70], bg=bg, subtitle=subtitle[:60]))

    def _quick_links(self):
        items = [
            ("Notice", "Click to check all Notice", "/events/notices/"),
            ("Apply Online", "Join SVU by applying online and pursue your desired course.", "/admission/apply/"),
            ("University Scholarship Foundation",
             "The University Scholarship Foundation offers scholarships to meritorious students under special categories.",
             "/page/scholarships/"),
            ("Schools & Courses", "SVU schools offer multiple courses to identify and support pupil's diverse learning needs.", "/academics/courses/"),
            ("Industry Partners", "An interesting challenge in developing skills for youth and creating a strong pipeline of talent is a seemingly…", "/academics/industry-partners/"),
            ("SVU Facilities", "The Swami Vivekananda University has one of the best-in-class infrastructure and facilities on the campus.", "/academics/facilities/"),
        ]
        for order, (title, desc, url) in enumerate(items):
            QuickLink.objects.get_or_create(
                title=title, defaults={"description": desc, "url": url, "order": order}
            )

    def _offerings(self):
        items = [
            ("Curriculum", "curriculum", "SVU is committed to provide an effective and dynamic curriculum with a distinctive mission to transform lives through education."),
            ("Tech Classroom", "classroom", "The digital whiteboards make learning methods to be the most interactive. Our faculty provides academic training through smart classrooms."),
            ("Experts", "experts", "SVU's course features expert faculty to impart quality training to the students."),
            ("Digital Library", "library", "We are pleased to offer an online storehouse of knowledge to maintain text-books, notes, journals, e-thesis, maps, rare books, and other important documents with the advent of digital technology!"),
        ]
        for order, (title, icon, desc) in enumerate(items):
            Offering.objects.get_or_create(
                title=title, defaults={"icon": icon, "description": desc, "order": order}
            )

    def _enlistments(self):
        items = [
            ("AIMA MAT (for admission to MBA)", "AIMA", "All India Management Association logo", (0, 90, 170), (238, 238, 238)),
            ("UCEED 2026 (for admission to B.Des)", "UCEED", "UCEED 2026 logo", (232, 160, 20), (253, 243, 220)),
            ("CLAT 25 (for admission to Law programs)", "CLAT", "Consortium of National Law Universities logo", (20, 50, 110), (238, 238, 238)),
        ]
        for order, (title, short, alt, fg, bg) in enumerate(items):
            item, created = Enlistment.objects.get_or_create(
                title=title, defaults={"alt_text": alt, "order": order}
            )
            attach(item, "logo", f"enlist-{short.lower()}.png", make_logo(short, bg=bg, fg=fg))

    def _programs(self):
        data = [("UG", "Under Graduate programmes"), ("PG", "Post Graduate programmes"),
                ("PhD", "Doctoral research programmes"), ("Diploma", "Diploma & certificate programmes")]
        programs = {}
        for order, (name, desc) in enumerate(data):
            program, _ = Program.objects.get_or_create(
                name=name, defaults={"description": desc, "order": order}
            )
            programs[name] = program
        return programs

    def _schools(self):
        schools = []
        for order, (name, desc, bg) in enumerate(SCHOOLS):
            school, created = School.objects.get_or_create(
                name=name,
                defaults={
                    "short_description": desc,
                    "order": order,
                    "description": f"<p>{desc}</p><p>The {name} at Swami Vivekananda University "
                                   "combines an NEP-2020 aligned curriculum with in-curriculum "
                                   "internships, global exposure and industry-oriented projects.</p>",
                    "meta_description": desc[:290],
                },
            )
            attach(school, "card_image", f"school-{order + 1}.jpg",
                       make_card(name.replace(", ", ",\n").replace(" & ", " &\n"), bg=bg))
            schools.append(school)

            for dept_name in self._departments_for(name):
                Department.objects.get_or_create(
                    school=school, name=dept_name,
                    defaults={"description": f"<p>Department of {dept_name}, {name}.</p>"},
                )
        return schools

    @staticmethod
    def _departments_for(school_name):
        mapping = {
            "School of Engineering": ["Computer Science & Engineering", "Electronics & Communication Engineering", "Civil Engineering", "Mechanical Engineering"],
            "School of Management & Commerce": ["Management Studies", "Commerce", "Economics"],
            "School of Law": ["Law"],
            "School of Arts, Media & Design": ["Journalism & Mass Communication", "Design", "Fine Arts", "Animation & Graphics"],
            "School of Nursing, Health & Pharmaceutical Sciences": ["Nursing", "Pharmacy", "Optometry", "Medical Laboratory Sciences"],
            "School of Science & Technology": ["Physics", "Chemistry", "Mathematics & Computing", "Statistics & Data Science"],
            "School of Life, Agricultural & Biotechnological Sciences": ["Biotechnology", "Microbiology", "Bioinformatics", "Agriculture"],
            "School of Humanities, Languages and Social Sciences": ["English", "History", "Political Science", "Sociology", "Psychology"],
            "School of Lifelong Learning": ["Continuing Education"],
        }
        return mapping.get(school_name, [])

    def _courses(self, schools, programs):
        for order, (school_index, program_key, name, duration) in enumerate(COURSES):
            school = schools[school_index]
            Course.objects.get_or_create(
                school=school, name=name, program=programs[program_key],
                defaults={
                    "duration": duration,
                    "order": order,
                    "is_featured": order < 6,
                    "eligibility": "<p>Candidates must have passed 10+2 (or equivalent) from a "
                                   "recognised board with the required subject combination. "
                                   "Merit scholarships are available for eligible applicants.</p>",
                    "description": f"<p>{name} at {school.name}, Swami Vivekananda University. "
                                   "The programme is NEP-2020 aligned with AI-integrated "
                                   "coursework, in-curriculum internships and industry projects.</p>",
                    "department": school.departments.first(),
                },
            )

    def _videos(self):
        items = [
            ("Swami Vivekananda University", "Top University in Kolkata", "aqz-KE-bpKQ"),
            ("SVU Ranked Among Top 10", "Media Colleges in India", "ScMzIvxBSi4"),
        ]
        for order, (title, highlight, video_id) in enumerate(items):
            VideoFeature.objects.get_or_create(
                title=title,
                defaults={"highlight": highlight, "youtube_id": video_id, "order": order},
            )

    def _chancellor(self):
        message, created = ChancellorMessage.objects.get_or_create(
            name="The Chancellor",
            defaults={
                "excerpt": ("Swami Vivekananda University continues to grow from strength to "
                            "strength, consistently endeavouring to provide its students "
                            "with unmatched opportunities to excel."),
                "full_message": ("<p>Swami Vivekananda University continues to grow from strength to "
                                 "strength with every passing year.</p><p>We consistently endeavour to "
                                 "provide our students with unmatched opportunities to excel — "
                                 "through an industry-aligned curriculum, global exposure and a "
                                 "culture of research and entrepreneurship.</p>"),
            },
        )
        attach(message, "photo", "chancellor.jpg", make_portrait("SVU Chancellor"))

    def _centres(self):
        items = [
            ("Centre for Innovation & Entrepreneurship", "innovation",
             "It aims at fuelling the principal ambitions of the students by developing innovative thinking, and by stimulating entrepreneurial skills."),
            ("Industry Collaboration", "industry",
             "We believe that students require proper grooming along with quality academic input to become industry ready. With this view, the university offers Industry Connect Program."),
            ("Centre of Excellence", "excellence",
             "The Centre of Excellence established in 2018 at SWAMI VIVEKANANDA UNIVERSITY aims at fuelling the principal ambitions of the student. The entity nurtures and builds the aspiration to achieve."),
            ("Swami Vivekananda Centre for Women Studies", "women",
             "Centre for Women's Studies at SVU seeks to provide an interdisciplinary and comparative framework for the students to study gender related aspects."),
        ]
        for order, (title, icon, desc) in enumerate(items):
            Centre.objects.get_or_create(
                title=title, defaults={"icon": icon, "description": desc, "order": order}
            )

    def _testimonials(self):
        items = [
            ("Poulomi Paul", "Dept of Journalism and Mass Communication",
             "SVU consistently provided us with opportunities to enhance my skills beyond the "
             "classroom. Whether through industry interface or focused internship programs, this "
             "proactive approach to learning helped me secure a position as a Trainee Account "
             "Executive with India's Leading PR Agency in Mumbai."),
            ("Abhijit Parira", "Dept of Journalism and Mass Communication",
             "I was always passionate about news and its technical aspect but was unsure to take "
             "up Media Studies. After visiting a couple of media colleges, I walked into the "
             "campus of Swami Vivekananda University and felt that it was the right place for my "
             "studies. Today, I am working with a national news channel."),
            ("Sujal Shaw", "B.Tech CSE",
             "I am a student of B.Tech (CSE). I am excited to share that I have landed a "
             "placement in both LLOYD LEE COMPANY AND TCS (TATA CONSULTANCY SERVICES). This is "
             "possible because of the immense support of the faculty of the Computer Science "
             "Department."),
        ]
        for order, (name, department, quote) in enumerate(items):
            person, created = Testimonial.objects.get_or_create(
                name=name, defaults={"department": department, "quote": quote, "order": order}
            )
            attach(person, "photo", f"student-{order + 1}.jpg", make_portrait(name))

    def _footer_links(self):
        useful = [
            ("About Us", "/page/about-svu/"), ("Contact Us", "/contact/"),
            ("Our Courses", "/academics/courses/"), ("Job Opportunities", "/page/careers/"),
            ("Public Self-Disclosure", "/page/public-self-disclosure/"), ("Blog", "/page/blog/"),
            ("SVU-IBSC", "/page/svu-ibsc/"),
            ("COMMUNICATION : SVU's Academic Media Journal", "/page/communication-journal/"),
            ("Purchase RFP/RFQ", "/page/purchase-rfp/"),
            ("Terms & Conditions", "/page/terms-conditions/"),
            ("Fee Refund Policy", "/page/fee-refund-policy/"),
        ]
        external = [
            ("UGC", "https://www.ugc.gov.in/"),
            ("UGC e-samadhan", "https://www.ugc.gov.in/e-samadhan"),
            ("Ministry of Education", "https://www.education.gov.in/"),
            ("Shodhganga", "https://shodhganga.inflibnet.ac.in/"),
            ("Shodhgangotri", "https://shodhgangotri.inflibnet.ac.in/"),
            ("Handbook on Basics of Cyber Hygiene for Higher Education Institutions",
             "https://www.ugc.gov.in/"),
        ]
        for order, (title, url) in enumerate(useful):
            FooterLink.objects.get_or_create(
                title=title, section=FooterLink.SECTION_USEFUL,
                defaults={"url": url, "order": order},
            )
        for order, (title, url) in enumerate(external):
            FooterLink.objects.get_or_create(
                title=title, section=FooterLink.SECTION_EXTERNAL,
                defaults={"url": url, "order": order, "open_in_new_tab": True},
            )

    def _notices(self):
        today = timezone.localdate()
        items = [
            ("NOTICE- Nasha Mukta Yuva for Vikshit Bharat Sankalp Abhiyan", today, True),
            ("Result for JRF Advertisement- Shayani Dasgupta", today - timezone.timedelta(days=16), False),
            ("Declaration of Public Holiday on July 6, 2026, marking the 125th Birth "
             "Anniversary of Dr. Syama Prasad Mookerjee",
             today - timezone.timedelta(days=35), False),
            ("Notice regarding Odd Semester Examination Schedule 2026-27",
             today - timezone.timedelta(days=48), False),
            ("Anti-Ragging Awareness Week — mandatory undertaking submission",
             today - timezone.timedelta(days=60), False),
            ("Scholarship disbursement schedule for merit category students",
             today - timezone.timedelta(days=75), False),
        ]
        for title, date, important in items:
            Notice.objects.get_or_create(
                title=title,
                defaults={"notice_date": date, "is_important": important,
                          "summary": f"<p>{title}</p>"},
            )

    def _events(self):
        today = timezone.localdate()
        items = [
            ("Swami Vivekananda University celebrated the 77th Republic Day on campus with "
             "patriotic fervour. The ceremony featured an NCC parade, unfurling of the national "
             "flag, cultural performances by cadets", 12),
            ("What an incredible evening! The Department of Sociology, Swami Vivekananda "
             "University, proudly presented RENAISSANCE 3.0 2025", 26),
            ("Swami Vivekananda University warmly welcomed esteemed delegates from Japan!", 40),
            ("Swami Vivekananda University, one of the Eastern India's leading multidisciplinary "
             "universities, has entered into a strategic collaboration with Greenax Services "
             "Pvt. Ltd.", 55),
            ("Swami Vivekananda University had the privilege of hosting an exclusive session with "
             "H.E. Mr. Bishnu Prasad Gautam, Ambassador of Nepal to India", 70),
            ("Upcoming event — Faculty development programme organised by Department of "
             "Sociology: SVU Intersectionality on methods beyond singles — Axis thinking", 84),
            ("Convocation 2026 — Swami Vivekananda University confers degrees on the graduating "
             "batch across all schools", 96),
        ]
        for order, (title, days_ago) in enumerate(items):
            event, created = Event.objects.get_or_create(
                title=title,
                defaults={
                    "event_date": today - timezone.timedelta(days=days_ago),
                    "venue": "SVU Campus, New Town, Kolkata",
                    "is_featured": order < 3,
                    "description": f"<p>{title}</p><p>The programme saw enthusiastic "
                                   "participation from students, faculty members and invited "
                                   "guests across departments.</p>",
                },
            )
            attach(event, "cover_image", f"event-{order + 1}.jpg",
                       make_photo(f"SVU Event {order + 1}"))

    def _geography(self):
        for state_order, (state_name, cities) in enumerate(sorted(STATES.items())):
            state, _ = State.objects.get_or_create(
                name=state_name, defaults={"order": state_order}
            )
            for city_order, city_name in enumerate(cities):
                City.objects.get_or_create(
                    state=state, name=city_name, defaults={"order": city_order}
                )

    def _pages(self):
        pages = [
            ("About SVU", "about-svu",
             "<p>Swami Vivekananda University (SVU) is a state private university built on the "
             "ideals and teachings of Swami Vivekananda.</p><h2>Our promise</h2><ul><li>NEP-2020 aligned curriculum</li>"
             "<li>AI-integrated courses across disciplines</li><li>In-curriculum internships</li>"
             "<li>Global exposure and industry-oriented programmes</li>"
             "<li>Scholarships up to 100%</li></ul>"),
            ("Chancellor's Message", "chancellors-message",
             "<p>Swami Vivekananda University that commenced its journey as the youngest "
             "university in West Bengal in 2017, has completed yet another year successfully, "
             "consistently endeavouring to provide its students with unmatched opportunities to "
             "excel.</p><p>— The Chancellor, Swami Vivekananda University</p>"),
            ("Privacy Policy", "privacy-policy",
             "<h2>What we collect</h2><p>When you submit the enquiry or contact form we collect "
             "your name, e-mail address, mobile number, location and programme of interest, "
             "along with your consent record, the page you submitted from, your IP address and "
             "browser user-agent. The last three are kept purely as an anti-abuse audit "
             "trail.</p>"
             "<h2>Why we collect it</h2><p>Solely to respond to your admission enquiry. We never "
             "sell your data and never share it with third-party marketers.</p>"
             "<h2>How long we keep it</h2><p>Enquiries and contact messages are automatically "
             "purged after 24 months.</p>"
             "<h2>Cookies</h2><p>We set only a session cookie and a CSRF cookie — both are "
             "strictly necessary for the site to work securely. We run no third-party "
             "advertising or analytics cookies.</p>"
             "<h2>Your rights</h2><p>Write to us to access, correct or delete the personal data "
             "we hold about you.</p>"),
            ("Terms & Conditions", "terms-conditions",
             "<p>By using this website you agree to use it lawfully and not to attempt to gain "
             "unauthorised access to any part of it. Content is the property of Swami Vivekananda "
             "University unless stated otherwise.</p>"),
            ("Fee Refund Policy", "fee-refund-policy",
             "<p>Fee refunds are processed in line with the UGC refund policy notification. "
             "Applications for refund must be submitted in writing to the Accounts "
             "Department.</p>"),
            ("UGC Compliance Documents", "ugc-compliance",
             "<p>Statutory documents and disclosures mandated by the University Grants "
             "Commission are published on this page.</p>"),
            ("Public Self-Disclosure", "public-self-disclosure",
             "<p>Institutional information published under the UGC public self-disclosure "
             "requirement.</p>"),
            ("Scholarships", "scholarships",
             "<p>The University Scholarship Foundation offers scholarships to meritorious students "
             "under special categories. Merit scholarships of up to 100% are available.</p>"),
            ("IQAC", "iqac",
             "<p>The Internal Quality Assurance Cell (IQAC) works towards continuous "
             "improvement of the academic and administrative performance of the university.</p>"),
            ("NIRF", "nirf",
             "<p>National Institutional Ranking Framework data templates and submissions.</p>"),
            ("WILP", "wilp",
             "<p>The Work Integrated Learning Programme (WILP) allows working professionals to "
             "pursue a degree alongside employment.</p>"),
            ("Anti-Ragging Committee", "anti-ragging",
             "<p>Swami Vivekananda University maintains a strict zero-tolerance policy on ragging. "
             "The Anti-Ragging Committee and Squad monitor the campus and hostels "
             "continuously.</p>"),
        ]
        for title, slug, content in pages:
            Page.objects.get_or_create(
                slug=slug,
                defaults={"title": title, "content": content,
                          "meta_description": f"{title} — Swami Vivekananda University, Kolkata."},
            )

    def _faqs(self):
        items = [
            ("Admission", "When do admissions for 2026-27 open?",
             "<p>Admissions for the 2026-27 session are open now. Apply online or call our "
             "toll-free admission helpline.</p>"),
            ("Admission", "Does SVU take admission through agents or consultants?",
             "<p>No. SVU does not take admission through any agents or consultants. Please refer "
             "to the SVU website only for any admission-related query.</p>"),
            ("Admission", "What entrance exams does SVU accept?",
             "<p>AIMA MAT for MBA, UCEED for B.Des and CLAT for law programmes.</p>"),
            ("Fees & Scholarships", "Are scholarships available?",
             "<p>Yes — merit scholarships of up to 100% are offered, along with special-category "
             "scholarships from the University Scholarship Foundation.</p>"),
            ("Campus", "Is hostel accommodation available?",
             "<p>Yes, separate hostel accommodation is available for male and female students "
             "with 24x7 security and dining facilities.</p>"),
            ("Placements", "What is the highest placement package?",
             "<p>The highest placement package recorded is 51 LPA.</p>"),
        ]
        for order, (category, question, answer) in enumerate(items):
            FAQ.objects.get_or_create(
                question=question,
                defaults={"answer": answer, "category": category, "order": order},
            )

    def _admission_extras(self):
        steps = [
            ("Fill the enquiry form", "Share your details and programme of interest so our "
                                      "admission counsellors can reach you."),
            ("Submit your application", "Complete the online application form and upload your "
                                        "academic documents."),
            ("Counselling & document verification", "Attend the counselling session; original "
                                                    "documents are verified at this stage."),
            ("Pay the fee and confirm your seat", "Pay the admission fee online to confirm your "
                                                  "seat and receive your enrolment number."),
        ]
        for order, (title, description) in enumerate(steps):
            AdmissionStep.objects.get_or_create(
                title=title, defaults={"description": description, "order": order}
            )

        scholarships = [
            ("Merit Scholarship", "Up to 100%",
             "Awarded on the basis of qualifying examination marks and entrance performance."),
            ("University Scholarship Foundation Award", "Special categories",
             "For meritorious students under special categories including single girl child, "
             "wards of defence personnel and differently-abled applicants."),
            ("Sports Scholarship", "Up to 50%",
             "For students representing the state or country in recognised sporting events."),
        ]
        for order, (title, percentage, description) in enumerate(scholarships):
            Scholarship.objects.get_or_create(
                title=title,
                defaults={"percentage": percentage, "description": description, "order": order},
            )

    def _facilities_partners(self):
        facilities = [
            ("Digital Library", "An online storehouse of textbooks, notes, journals, e-thesis, "
                                "maps and rare books."),
            ("Smart Classrooms", "Digital whiteboards make learning interactive across every "
                                 "lecture hall."),
            ("Laboratories", "Well-equipped engineering, science, pharmacy and nursing "
                             "laboratories."),
            ("Hostel", "Separate, secure hostel accommodation for male and female students."),
            ("Sports Complex", "Indoor and outdoor sporting facilities including a gymnasium."),
            ("Cafeteria", "Multi-cuisine cafeteria serving hygienic and affordable meals."),
        ]
        for order, (title, description) in enumerate(facilities):
            facility, created = Facility.objects.get_or_create(
                title=title, defaults={"description": f"<p>{description}</p>", "order": order}
            )
            attach(facility, "image", f"facility-{order + 1}.jpg", make_photo(title))

        partners = ["TCS", "Wipro", "Cognizant", "Capgemini", "Deloitte", "ITC", "Byju's", "Amazon"]
        for order, name in enumerate(partners):
            partner, created = IndustryPartner.objects.get_or_create(
                name=name, defaults={"order": order}
            )
            attach(partner, "logo", f"partner-{order + 1}.png",
                       make_logo(name, size=(300, 200), fg=(40, 40, 40)))
