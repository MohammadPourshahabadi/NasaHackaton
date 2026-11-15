"""Small offline conversation flow for Aboard's English-language assistant."""

from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class Reply:
    text: str
    action: str = 'none'
    fields: dict = field(default_factory=dict)


WELCOME = ('Welcome aboard. I can help with your daily check-in. Tell me how you feel, '
           'ask for a measurement guide, or ask to attach an image.')
SLEEP_QUESTION = 'How many hours did you sleep last night? An estimate is fine.'
FATIGUE_QUESTION = 'How tired do you feel right now, from one for low fatigue to five for high fatigue?'
UPLOAD_QUESTION = 'Is it an injury photo or an ultrasound export?'
HELP = ('Try “I feel sleepy,” “open my check-in,” “show the blood pressure guide,” '
        'or “upload an ultrasound.” During a check-in you can also say “skip,” “repeat,” or “cancel.”')

DEFAULT_CHOICES = (
    'hey aboard', 'hello aboard', 'I feel sleepy', 'I feel like sleepy', 'I am feeling tired',
    'I feel fatigued', 'start my daily check in', 'open my check in', 'show the blood pressure guide',
    'show me how to take my pulse', 'how do I take my temperature', 'show the sleep guide',
    'show the ultrasound guide', 'upload a photo', 'attach a picture of my injury',
    'upload an injury photo', 'I want to upload a picture of my injury',
    'upload an ultrasound', 'I want to upload an ultrasound picture', 'attach an ultrasound image',
    'I need help now', 'I need urgent help', 'I have chest pain', 'I cannot breathe', 'help', 'cancel', 'repeat',
)

# These are examples for a simulated escalation path. Crew procedures define real operations.
# https://www.nasa.gov/reference/3-0-health-and-medical-care/
# https://www.heart.org/en/about-us/heart-attack-and-stroke-symptoms
URGENT = re.compile(
    r'\b(?:chest\s+(?:pain|pressure|tightness|discomfort)|(?:my\s+)?chest\s+hurts|'
    r'(?:pain|pressure|tightness|discomfort)\s+in\s+(?:my|the)\s+chest|'
    r'short(?:ness)?\s+of\s+breath|(?:can\s*not|can\'t|couldn\'t|struggl\w*\s+to)\s+breathe|'
    r'(?:difficulty|trouble|problems?)\s+breathing|'
    r'face\s+droop\w*|slurred\s+speech|one-sided\s+weakness|'
    r'(?:uncontrolled|heavy|severe)\s+bleeding|bleeding\s+(?:heavily|a\s+lot|(?:won\'t|will\s+not)\s+stop)|'
    r'(?:passed\s+out|fainted|unresponsive|lost\s+consciousness)|'
    r'(?:medical\s+)?emergency|(?:need|send|get|call)\s+(?:medical\s+)?help\s+(?:now|immediately)|'
    r'(?:need|want)\s+(?:immediate|urgent)\s+(?:help|medical\s+attention))\b'
)
DENIAL = re.compile(r"\b(?:no|without|denies|(?:don't|do\s+not|didn't|did\s+not)\s+(?:have|feel|experience)|"
                    r"(?:am\s+not|i'm\s+not)\s+(?:having|feeling|experiencing)|not\s+an?)"
                    r"(?:\s+\w+){0,3}\s*$")
UPLOAD = re.compile(r'\b(?:upload\w*|attach\w*|add|import|share|submit|send|select|choose)\b')
PHOTO = re.compile(r'\b(?:photos?|pictures?|pics?|images?|jpe?gs?|pngs?|screenshots?)\b')
ULTRASOUND = re.compile(r'\b(?:ultra\s*sound|sonogram|sonograph\w*|echo\s*cardiogram|scan)\b')
INJURY = re.compile(r'\b(?:injur\w*|wound\w*|bruis\w*|cut|scrape|rash|burn|swelling)\b')
GUIDE = re.compile(r'\b(?:guide|tutorial|walkthrough|instructions|teach|demonstrate|how\s+(?:do|can|should|to)|show\s+me\s+how)\b')
FATIGUE = re.compile(r'\b(?:sleepy|tired(?:ness)?|fatigu\w*|exhaust\w*|drows\w*|sleep\s+deprived|poor\s+sleep|'
                     r'slept\s+badly|didn\'t\s+sleep\s+well|struggl\w*\s+to\s+stay\s+awake)\b')
CHECKIN = re.compile(r'\b(?:check[ -]?in|daily\s+(?:questionnaire|check)|log\s+my\s+readings)\b')

NUMBERS = dict(zip(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
    'seventeen eighteen nineteen twenty'.split(), range(21),
)) | {'thirty': 30, 'forty': 40, 'fifty': 50}
SPOKEN_LOOKUP = re.compile(r'\b(?:' + '|'.join(NUMBERS) + r')\b')
HOURS = re.compile(r'(?<![\d.\-])(\d{1,2}(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b'
                   r'(?:\s*(?:and\s+)?(\d{1,2})\s*(?:minutes?|mins?|m)\b)?')
MINUTES = re.compile(r'(?<![\d.\-])(\d{1,2})\s*(?:minutes?|mins?|m)\b')
RATING = re.compile(r'(?<![\d.\-])([1-5])\s*(?:out\s+of\s+(?:5|five)|/\s*5)\b')
FATIGUE_RATING = re.compile(r'\b(?:fatigue(?:\s+(?:rating|level))?|tiredness)\s*(?:[=:]|is|was|at|of|around)?\s*'
                            r'([1-5])(?![\d.])\b')
MEASUREMENT_GUIDES = (
    (re.compile(r'\b(?:blood\s+pressure|cuff|bp)\b'), 'bp', 'blood pressure'),
    (re.compile(r'\b(?:pulse|heart\s+rate)\b'), 'pulse', 'pulse'),
    (re.compile(r'\b(?:temperature|thermometer)\b'), 'temperature', 'temperature'),
    (ULTRASOUND, 'ultrasound', 'ultrasound'),
    (re.compile(r'\b(?:sleep|tired|fatigue)\b'), 'sleep', 'sleep and fatigue'),
)


def normalize(text):
    normalized = re.sub(r'\s+', ' ', text.lower().replace('’', "'")).strip()
    return re.sub(r"^(?:(?:hey|hello|okay|ok),?\s+)?aboard\b[ ,:!?-]*", '', normalized).strip()


def urgent_request(text):
    # A denial in one clause cannot suppress a symptom in another clause.
    for clause in re.split(r'[,.;!?]|\b(?:but|however|although|and)\b(?=\s+\w)', text):
        for match in URGENT.finditer(clause):
            preceding = clause[:match.start()]
            if not DENIAL.search(preceding):
                return True
    return False


def numeric_text(text):
    text = re.sub(r'\b(twenty|thirty|forty|fifty)[ -](one|two|three|four|five|six|seven|eight|nine)\b',
                  lambda match: str(NUMBERS[match[1]] + NUMBERS[match[2]]), text)
    text = SPOKEN_LOOKUP.sub(lambda match: str(NUMBERS[match[0]]), text)
    text = re.sub(r'\b(\d+)\s+point\s+(\d+)\b', r'\1.\2', text)
    text = re.sub(r'\b(\d+)\s+and\s+(?:a\s+)?half\b', r'\1.5', text)
    return text


def sleep_hours(text, *, allow_bare=False):
    if re.search(r"\b(?:no sleep|didn't sleep|did not sleep|couldn't sleep|could not sleep)\b", text):
        if not re.search(r'\b(?:well|much|enough)\b', text):
            return 0.0
    text = numeric_text(text)
    match = HOURS.search(text)
    if match:
        minutes = int(match[2] or 0)
        hours = float(match[1]) + minutes / 60
        return round(hours, 2) if hours <= 24 and minutes < 60 else None
    if re.search(r'\bhalf\s+(?:an?\s+)?hour\b', text):
        return 0.5
    if allow_bare:
        match = re.fullmatch(r'(?:about\s+|around\s+|maybe\s+|roughly\s+)?(\d{1,2}(?:\.\d+)?)\s*[.!]?', text)
        if match:
            hours = float(match[1])
            return hours if hours <= 24 else None
        match = MINUTES.search(text)
        if match:
            return round(int(match[1]) / 60, 2)
    return None


def fatigue_rating(text, *, allow_bare=False):
    text = numeric_text(text)
    match = RATING.search(text) or FATIGUE_RATING.search(text)
    if not match and allow_bare:
        match = re.fullmatch(r"(?:(?:i\s+would|i'd)\s+(?:say|rate\s+it|give\s+it)\s+)?"
                             r'(?:a\s+|about\s+|around\s+|maybe\s+)?([1-5])\s*[.!]?', text)
    return int(match[1]) if match else None


class CrewDialogue:
    """Session-local dialogue. Only the caller opens windows or saves data."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.pending = None
        self.upload_pending = False
        self.draft = {}

    def welcome(self):
        return WELCOME

    def clear_upload_choice(self):
        """Dismiss the image type prompt while preserving pending check-in answers."""
        self.upload_pending = False

    def choices(self):
        """Utterance examples for a speech recognizer and optional quick replies."""
        if self.upload_pending:
            return ('injury photo', 'an image of my injury', 'ultrasound', 'an ultrasound export', *DEFAULT_CHOICES)
        if self.pending == 'sleep':
            answers = tuple(f'{word} hours' for word, hours in NUMBERS.items() if hours <= 20)
            return (*answers, 'five and a half hours', 'seven and a half hours', 'half an hour',
                    'I slept five hours', 'no sleep', 'skip', *DEFAULT_CHOICES)
        if self.pending == 'fatigue':
            answers = tuple(NUMBERS)[1:6]
            return (*answers, *(f'{word} out of five' for word in answers), 'skip', *DEFAULT_CHOICES)
        return DEFAULT_CHOICES

    def finish_checkin(self):
        values = self.draft.copy()
        self.reset()
        message = ('I’ve added your answers to the check-in. Review them and add your other readings when you’re ready.'
                   if values else 'I’ve opened your daily check-in. You can enter readings when you’re ready.')
        return Reply(message, 'open_checkin', values)

    def respond(self, raw_text):
        text = normalize(raw_text)
        command = text.strip(' .!?')
        if urgent_request(text):
            self.reset()
            return Reply('Alert the crew medical officer now and follow your mission emergency procedure. '
                         'I’m opening the urgent response guide.', 'urgent', {'urgent': True, 'notes': raw_text.strip()})

        if command in ('cancel', 'stop', 'start over', 'reset', 'never mind', 'nevermind'):
            self.reset()
            return Reply('Okay. We can start again whenever you’re ready.')
        if command in ('help', 'what can you do', 'show commands'):
            return Reply(HELP)
        if command in ('repeat', 'say that again', 'repeat the question', 'what was the question'):
            if self.upload_pending:
                return Reply(UPLOAD_QUESTION)
            return Reply({'sleep': SLEEP_QUESTION, 'fatigue': FATIGUE_QUESTION}.get(self.pending, WELCOME))
        if not command or command in ('hi', 'hello', 'hey', 'good morning', 'good afternoon'):
            return Reply(self.welcome())

        # An upload request can interrupt a check-in without discarding collected answers.
        ultrasound, injury, photo = ULTRASOUND.search(text), INJURY.search(text), PHOTO.search(text)
        upload = (UPLOAD.search(text) and (ultrasound or photo or injury or 'file' in text or command in ('upload', 'attach'))
                  or (photo and re.search(r'\b(?:open|take|load)\b', text) and not GUIDE.search(text)))
        if self.upload_pending or upload:
            if ultrasound and (self.upload_pending or not injury or not re.search(r'\bor\b', text)):
                self.upload_pending = False
                return Reply('I’ll open the ultrasound upload. Choose an exported PNG or JPEG, then review its preview.',
                             'upload_ultrasound')
            if injury and not ultrasound:
                self.upload_pending = False
                return Reply('I’ll open the injury photo upload. Choose a clear PNG or JPEG and review the preview.',
                             'upload_injury')
            if upload:
                self.upload_pending = True
                return Reply(UPLOAD_QUESTION, 'upload_choice')

        if GUIDE.search(text):
            for pattern, name, label in MEASUREMENT_GUIDES:
                if pattern.search(text):
                    return Reply(f'Opening the {label} guide. You can play it or step through it.', f'guide_{name}')
        if CHECKIN.search(text) and not FATIGUE.search(text):
            return self.finish_checkin()

        skip = command in ('skip', 'pass', 'unknown', "i don't know", 'i do not know', 'unsure')
        if self.pending == 'sleep':
            hours = sleep_hours(text, allow_bare=True)
            if hours is not None or skip:
                if hours is not None:
                    self.draft['sleep'] = hours
                rating = fatigue_rating(text)
                if rating is not None:
                    self.draft['fatigue'] = rating
                    return self.finish_checkin()
                self.pending = 'fatigue'
                return Reply(FATIGUE_QUESTION)
            return Reply('Give me an estimate in hours, like five and a half, or say skip.')
        if self.pending == 'fatigue':
            rating = fatigue_rating(text, allow_bare=True)
            if rating is not None or skip:
                if rating is not None:
                    self.draft['fatigue'] = rating
                return self.finish_checkin()
            return Reply('Please say a number from one to five. Five means very tired. You can also say skip.')

        if FATIGUE.search(text) or re.search(r'\bi\s+slept\b', text):
            self.draft['notes'] = raw_text.strip()
            hours = sleep_hours(text)
            rating = fatigue_rating(text)
            if hours is not None:
                self.draft['sleep'] = hours
            if rating is not None:
                self.draft['fatigue'] = rating
            if hours is not None and rating is not None:
                return self.finish_checkin()
            self.pending = 'sleep' if hours is None else 'fatigue'
            question = SLEEP_QUESTION if hours is None else FATIGUE_QUESTION
            return Reply(f'Thanks for telling me. {question}')

        return Reply('I didn’t catch a check-in or upload request. Say “I feel sleepy,” “upload an injury photo,” or “help.”')


def self_test():
    crew = CrewDialogue()
    assert crew.respond('Hey Aboard, I feel like sleepy').action == 'none'
    assert 'five hours' in crew.choices()
    assert crew.respond('I slept five and a half hours').text == FATIGUE_QUESTION
    assert crew.respond('please open a pop up to upload my ultrasound pic').action == 'upload_ultrasound'
    reply = crew.respond('four out of five')
    assert reply.action == 'open_checkin'
    assert reply.fields['sleep'] == 5.5 and reply.fields['fatigue'] == 4
    assert crew.respond('I want to upload a picture of her injury').action == 'upload_injury'
    assert crew.respond('upload an image').action == 'upload_choice'
    assert crew.respond('injury photo').action == 'upload_injury'
    assert crew.respond('show me how to measure blood pressure').action == 'guide_bp'
    assert crew.respond('open the ultrasound guide').action == 'guide_ultrasound'
    assert crew.respond('can I take a photo of my injury?').action == 'upload_injury'
    assert crew.respond("I'm tired but I can't breathe").action == 'urgent'
    assert crew.respond("I don't have chest pain, I just feel sleepy").action == 'none'
    assert crew.respond('skip').text == FATIGUE_QUESTION
    assert crew.respond('skip').action == 'open_checkin'
    assert crew.respond('I feel sleepy and slept five hours and thirty minutes, fatigue is four').fields['sleep'] == 5.5
    assert crew.respond('I want to upload my ultrasound and my chest hurts').action == 'urgent'
    assert crew.respond('I need help now, please').action == 'urgent'
    assert crew.respond("I'm not sure why I have chest pain").action == 'urgent'
    assert crew.respond("It's not an emergency, I'd like to open my check-in").action == 'open_checkin'
    assert crew.respond('upload an ultrasound picture of my injury').action == 'upload_ultrasound'
    assert sleep_hours('maybe twenty-five', allow_bare=True) is None
    assert sleep_hours('seven point five hours') == 7.5
    assert sleep_hours('I slept thirty minutes', allow_bare=True) == 0.5
    assert crew.respond('I feel sleepy and slept seven hours').text.endswith(FATIGUE_QUESTION)
    assert crew.respond("I'd give it a four.").fields['fatigue'] == 4
    print('Aboard conversation checks passed.')


if __name__ == '__main__':
    self_test()
