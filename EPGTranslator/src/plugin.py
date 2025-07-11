# -*- coding: utf-8 -*-
#

# for localized messages
from . import _

EPGTrans_vers = "3.02-release"

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import (config, ConfigSubsection,
 ConfigSelection, ConfigInteger, ConfigBoolean)
from Components.Label import Label
from Components.Language import language
from Components.ScrollLabel import ScrollLabel
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.StaticText import StaticText
from enigma import eEPGCache, eServiceReference, iPlayableService, iServiceInformation
from Plugins.Plugin import PluginDescriptor
from Screens.EventView import EventViewBase
from Screens.HelpMenu import HelpableScreen
from Screens.InfoBar import InfoBar
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.VirtualKeyBoard import VirtualKeyBoard

import re
import time
import os
import traceback

from .AutoflushCache import AutoflushCache
from .HTML5Entities import name2codepoint

# Python3 version
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

# Who we will pretend to be when calling translate.google.com
#
dflt_UA = 'OpenVix EPG Translator (Mozilla/5.0 compat): ' + EPGTrans_vers

# Useful constants for EPG fetching.
#
#   B = Event Begin Time
#   D = Event Duration
#   T = Event Title
#   S = Event Short Description
#   E = Event Extended Description
#   I = Event Id
#   N = Service Name

EPG_OPTIONS = 'BDTSEINX'    # X is not a returned-value setting

# Now split this into mnemonic indices, skipping any X
# Then we can use epg_T etc... and means that any change to EPG_OPTIONS
# is automatically handled
#
ci = 0
for i in list(range(len(EPG_OPTIONS))):
    if EPG_OPTIONS[i] == 'X':
        continue
    exec("epg_%s = %d" % (EPG_OPTIONS[i], ci))  # FIME : Refactor to not used exec
    ci += 1
epg_PB = ci  # Extra index for Playback Begin time.

# -*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
# Configuration settings.
#
# The list of available languages (sorted alphabetically)
#
langs = [
('af', _('Afrikaans')), ('sq', _('Albanian')), ('ar', _('Arabic')),
('az', _('Azerbaijani')), ('eu', _('Basque')), ('be', _('Belarusian')),
('bs', _('Bosnian')), ('bg', _('Bulgarian')), ('ca', _('Catalan')),
('ceb', _('Cebuano')), ('hr', _('Croatian')), ('cs', _('Czech')),
('da', _('Danish')), ('nl', _('Dutch')), ('en', _('English')),
('et', _('Estonian')), ('tl', _('Filipino')), ('fi', _('Finnish')),
('fr', _('French')), ('gl', _('Galician')), ('de', _('German')),
('el', _('Greek')), ('ht', _('Haitian Creole')), ('hu', _('Hungarian')),
('is', _('Icelandic')), ('id', _('Indonesian')), ('ga', _('Irish')),
('it', _('Italian')), ('jw', _('Javanese')), ('lv', _('Latvian')),
('lt', _('Lithuanian')), ('mk', _('Macedonian')), ('ms', _('Malay')),
('mt', _('Maltese')), ('no', _('Norwegian')), ('fa', _('Persian')),
('pl', _('Polish')), ('pt', _('Portuguese')), ('ro', _('Romanian')),
('ru', _('Russian')), ('sr', _('Serbian')), ('sk', _('Slovak')),
('sl', _('Slovenian')), ('es', _('Spanish')), ('sw', _('Swahili')),
('sv', _('Swedish')), ('tr', _('Turkish')), ('uk', _('Ukrainian')),
('ur', _('Urdu')), ('vi', _('Vietnamese')), ('cy', _('Welsh'))
]
# Sort this list using the user's default language.
#
langs = sorted(langs, key=lambda x: x[1])

rtol = {'ar', 'fa', 'ur'}


def get_lang(l):
    for x in langs:
        if x[0] == l:
            return x[1]
    return "Unknown"


# Source has an auto option in first place on the list
#
config.plugins.translator = ConfigSubsection()

# So we can use this to simplify (shorten) the rest of the code
#
CfgPlTr = config.plugins.translator

CfgPlTr.source = ConfigSelection(default='auto', choices=[('auto', _('Detect Language'))] + langs[:])

# Destination has no auto...
#
CfgPlTr.destination = ConfigSelection(default='en', choices=langs)
CfgPlTr.alternate = ConfigSelection(default='en', choices=langs)
CfgPlTr.start_EV_trans = ConfigBoolean(default=False)
CfgPlTr.timeout_hr = ConfigInteger(0, (0, 350))
CfgPlTr.showsource = ConfigSelection(default='yes', choices=[('yes', _('Yes')), ('no', _('No'))])
CfgPlTr.showtrace = ConfigBoolean(default=False)

curr_dest = CfgPlTr.destination.getValue()

# Now we have the config vars, create an AutoflushCache to hold the
# translations. We are storing tuples, so give a suitable null_return
#
AfCache = AutoflushCache(CfgPlTr.timeout_hr.getValue(), null_return=(None, None))

# Get the skin settings etc.
# These are defined wrt a FullHD setting, and will be scaled if
# the actual resolution differs.
#
from .Skin import MySD

# -*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
# Global functions
#

# ==================================================================
# Interpolate dynamic values using {xxx}.
# Used for skins, where time formats may contain %H:%M etc...,
# making % replacements a bit messy
#


def applySkinVars(skin, dict):
    for key in list(dict.keys()):   # Py3 needs the list, Py2 is OK with it
        try:
            skin = skin.replace('{' + key + '}', dict[key])
        except Exception as e:
            print(e, '@key=', key)
    return skin

# ==================================================================
# Translate HTML Entities (&xxx;) in text
# The standard python name2codepoint (in htmlentitydefs for Py2,
# html.entities for Py3) is incomplete, so we'll use a complete
# one (which is easy to create).
#


def transHTMLEnts(text):
    def repl(ent):              # The code for re.sub to run on matches
        res = ent.group(0)      # get the text of the match
        ent = res[1:-1].lower()  # Strip & and ;
        if re.match(r"#\d+", ent):  # Numeric entity
            res = chr(int(ent[1:]))
        else:
            try:                    # Look it up...
                res = chr(name2codepoint[ent])
            except:                 # Leave as-is
                pass
        return res
    text = re.sub("&.{,30}?;", repl, text)
    return str(text)

# ==================================================================
# A function to make a call to Google translate
# It may be dealing with only a sub-text of the original as
# DO_translation() will be splitting and long text and making
# multiple calls here.
# Spilt from DO_translation() to make the code more readable, and hence
# more easily maintained.
# This is the only code to know about the Web call and structure of the
# returned page.
#


def PART_translate(enc_text, source, dest):

# The /m url produces a smaller result to the "full" (/) page.
# It also (more importantly) actually returns the translated enc_text!
#
    url = 'https://translate.google.com/m?&sl=%s&tl=%s&q=%s' % (source, dest, enc_text)
    agents = {'User-Agent': dflt_UA}

# We'll extract the result from the returned web-page
# This is currently (07 Dec 2020) in a div with its last item making it
# a result-container...and we want everything up to the end of the div
# A hack (we don't parse the entire HTML), but simple.
#
    before_trans = 'class="result-container">'
    end_trans = '</div>'
    failed = True
    request = Request(url, headers=agents)
    try:
# Ensure the result is marked as utf-8 (Py2 needs it, Py3 doesn't, but
# doesn't object to the usage).
#
        output = urlopen(request, timeout=20).read().decode('utf-8')
        data = output[output.find(before_trans) + len(before_trans):]
        newtext = data.split(end_trans)[0]
        newtext = transHTMLEnts(newtext)
        failed = False
# Don't bother to distinguish error...
#
    except:
        newtext = ''    # leaving failed as True
    return (failed, newtext)


# ==================================================================
# We need to split on ".<whitespace>" and "<whitespace>", whilst
# remembering what the actual splitter was.
# So create the text patterns once.
#
enc_wspace = ''
enc_space = ''
nenc_sep = ''
for c in ([" ", "\n", "\t"]):   # Actually .<ws>
    enc_wspace = enc_wspace + nenc_sep + r'\.' + quote(c)
    enc_space = enc_space + nenc_sep + quote(c)
    nenc_sep = '|'

# The routine to actually sort out the translation of the text.
# This is NOT an object method, so that it can be called from "anywhere"
# This routine expects to get normal ("raw") text and will return the
# same.
# So *it* knows about URL encoding and HTMLEntity translation, so that
# the callers do not need to.
# It will split the incoming text (if necessary) into sub-texts of a
# length that Google translate can handle, then stitch them back
# together.
# The code tries to do such splitting at sentence boundaries (.<ws>) or
# failing that, at a word boundary (ws). If it can't do that it's
# en error.
#


def DO_translation(text, source, dest):     # source, dest are langs
    global enc_wspace, enc_space

# It seems that this incoming text may contain some EIT CR/LF sequences
# (see estring.cpp)
# So convert these to newlines now - they can end up being translated
# into other (displayed) characters
# Add any others to this list as required...
#
    for rpl in ("\xc2\x8a", "\xee\x82\x8a"):
        text = text.replace(rpl, "\n")

    enc_text = quote(text)
    enc_len = len(enc_text)
    max = 7000              # Less than the actual ~7656 to 7707
    nsplit = int(enc_len / max) + 1
    bsize = int(enc_len / nsplit) - 10

# We need to step along the string finding the longest match within the
# limits that ends a sentence.  Or, if we can't find a sentence end, at
# the end of a word.
#
    si = 0
    ei = len(enc_text) - 1
    togo = ei
    check_end = True
    res = ''

    while True:
# The running endpos is the lesser of si+bsize and ei
#
        ri = ei
        if ri > (si + bsize):
            ri = si + bsize

        if togo <= max:
            this_encpart = enc_text[si:]
            this_sep = ''
            this_len = len(this_encpart)
        else:
            split_re1 = "(?:(.{1,%s})(%s))" % (bsize, enc_wspace)
            split_re1 = re.compile(split_re1)
            match = split_re1.search(enc_text, si, ri)
            if match is None:
                split_re2 = "(?:(.{1,%s})(%s))" % (bsize, enc_space)
                split_re2 = re.compile(split_re2)
                match = split_re2.search(enc_text, si, ri)
            if match is None:
                res += "...unable to translate"
                break
            this_encpart = match.group(1)
            this_sep = unquote(match.group(2))
            this_len = len(this_encpart) + len(match.group(2))

# Translate the sub-text
#
        (failed, this_part) = PART_translate(this_encpart, source, dest)
        if failed:
            res += "...unable to translate"
            break

# Append the translated sub-text and the discovered separator
#
        res += this_part + this_sep
        si += this_len
        togo -= this_len
        if togo <= 0:
            break

# Iff the remaining quoted length is less than twice bsize then lower
# bsize, so we can't(?) end up with a very small final part.
#
        if check_end and (togo < bsize * 2):
            bsize = int(bsize * 2.0 / 3.0)
            check_end = False

    return res.strip()

# ==================================================================
# Regular expressions to split off the [] or () properties from a
# description. Used by EPGdata_translate().
#
# Make the props pattern usage depend on whether there is a [ within the
# first 12 characters or a ] within the last 12.
# For begin_props the last prop group must be [] (not ())
# For end_props the first prop group must be [] (not ())
#
# This will capture one whitespace from *after* the last prop, only if
# there is one.
#
# Also the compiled expression for the patterns.
#


# Patterns for matching [...] and (...)
# Interpolated into the working patterns using %s (so look out for them -
# do not confuse them with \s!)
#
sbk_prop = r'\[[^\]]*\]'     # Square brackets
par_prop = r'\([^\)]*\)'     # Parentheses

#
begin_props = r"""
^\s*                        # Strip any leading whitespace
(                           # Start all [] + () groups saving
 (?:                        # Start multi-groups
  (?:(?:%s|%s)\s*)          # Either grouping + whitespace
 )*                         # end a group - and repeat
 %s                         # last group - []
)                           # End all () or [] groups saving
\s*                         # Skip any intervening whitespace
(.*)                        # The real description
\s*$                        # Strip trailing whitespace to EOL
""" % (sbk_prop, par_prop, sbk_prop)
begin_matcher = re.compile(begin_props, flags=re.X | re.S)

end_props = r"""
^\s*                        # Strip any leading whitespace
(.*?)                       # The real description (? else it takes all)
\s*                         # Skip any intervening whitespace
(                           # Start all [] + () groups saving
 %s                         # first group - []
 \s*                        # Skip any intervening whitespace
 (?:                        # Start multi-groups
  (?:(?:%s|%s)\s*)          # Either grouping + whitespace
 )*                         # end a group - and repeat
 (?:\s*S\d+\s*Ep\d+)?       # UK ITV can have a trailing Sn Epn
)                           # End all () or [] groups saving
\s*$                        # Strip trailing whitespace to EOL
""" % (sbk_prop, sbk_prop, par_prop)
end_matcher = re.compile(end_props, flags=re.X | re.S)

# A string to use as a separator when the title and description are
# combined for a one-call translation.
# The idea is that it should be unchanged by the translation, but the
# code does attempt to handle things even if it is changed.
#
# Using "==========" or "&&&&&&&&&&" failed for some languages as only
# 9 of them came back, and with no following newline.
#
sepline = "**********"

# The actual code to translate the title and description.
#


def EPGdata_translate(title, descr, start, duration, uref):
    global sepline, begin_matcher, end_matcher

# Some descriptions (e.g. UK Freeview) may contain "properties" in [] at
# the end.  And so [S,AD] (subtitles, audio-description) end up being
# translated (e.g. for en -> de [S,AD] -> [TRAURIG]).
# So strip any such trailers before sending for translation then append
# them to the result.
#
    desc = descr.strip()
    prop = ''
    prepend_props = False
# Only check for props if we actually have a description
# Look for [ towards the beginning, to allow for an opening ()
    if len(descr) > 0:
        if '[' in descr[:12]:
            res = re.findall(begin_matcher, descr)
            if len(res) > 0:    # Only if findall succeeded
                (prop, desc) = res[0]
                prepend_props = True
# Look for ] towards the end, to allow for UK ITV Sn Epn
        elif ']' in descr[-12:]:
            res = re.findall(end_matcher, descr)
            if len(res) > 0:    # Only if findall succeeded
                (desc, prop) = res[0]

# We wish to translate the title and description in one call
# So we:
#   send sepline\n+title+\nsepline\n+desc
#   take the first line of what comes back
#   split the rest into two based on that first line
#
    r_text = sepline + "\n" + title + "\n" + sepline + "\n" + desc
    t_text = DO_translation(r_text, CfgPlTr.source.getValue(), curr_dest)

# Check that the first line is a set of "*"s (from sepline)
# The number of these may differ from that in sepline!
# That different number will be used for the second separator too.
#
    (t_sep, t_rest) = t_text.split("\n", 1)
    if re.match(r"[^*]", t_sep):  # Something not from sepline
        t_title = _("Translation error")
        t_descr = t_text
    else:
        try:
            (t_title, t_descr) = t_rest.split("\n" + t_sep + "\n", 1)
            if prop != "":
# prop will contain the "correct" trailing/whitespace
# But ignore props for an rtol language, as it will mess them up (may
# be messed up anyway, but no need to ensure it).
#
                if curr_dest not in rtol:
                    if prepend_props:
                        t_descr = prop + t_descr
                    else:
                        t_descr = t_descr + prop

# Work out a timeout for the result.
# If we have a specific timeout (in hours) use it, but if this is 0 set
# the timeout to when the programme will leave the EPG.
# But even a specific timeout should not extend beyond programme
# validity.
# A recording playback may have a PlayBack begin time, which we want to
# use as a cache basis (its original start time being useless for
# this).
#
            if start is None:   # A non-native recording?
                to = int(time.time() + 10800)
            else:
                to = int(start + duration + 60 * config.epg.histminutes.getValue())
            if CfgPlTr.timeout_hr.getValue() > 0:
                limit = int(time.time() + 3600 * CfgPlTr.timeout_hr.getValue())
                if limit < to:
                    to = limit
            AfCache.add(uref, (t_title, t_descr), abs_timeout=to)
        except Exception as e:  # Use originals on a failure...
            print('[EPGTranslator-Plugin] translateEPG, %s: "%s"' % (type(e).__name__, e))
            if (CfgPlTr.showtrace.getValue()):
                traceback.print_exc()
            (t_title, t_descr) = (title, descr)

    return (t_title, t_descr)

# ==================================================================
# Create a reference key for the cache.
# Done in one place to ensure consistency.
# Not a class method as it is called from multiple classes
#


def make_uref(sv_id, sv_name):
    return ":".join([curr_dest, str(sv_id), str(sv_name)])


# ==================================================================
# We need to know where we are to find the files relative to this
# script.
#
plugin_location = os.path.dirname(os.path.realpath(__file__))

# -*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
# Our classes
#


class TranslatorConfig(Setup):
    def __init__(self, session):
        Setup.__init__(self, session, "TranslatorConfig", plugin="Extensions/EPGTranslator", PluginLanguageDomain="EPGTranslator")
        self.setTitle(_("EPG Translator Setup - ") + EPGTrans_vers)
        CfgPlTr.timeout_hr.addNotifier(self.changeTimeout)

    def keyCancel(self):
        for x in self['config'].list:
            x[1].cancel()
        self.exit()

    def closeRecursive(self):
        self.keyCancel()

    def keySave(self):
        self.saveAll()
        self.exit()

    def exit(self):
        self.session.openWithCallback(self.close, TranslatorMain, None)

    def changeTimeout(self, configElement):
        AfCache.change_timeout(configElement.value)

    def __del__(self):
        CfgPlTr.timeout_hr.removeNotifier(self.changeTimeout)

# -*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-


class TranslatorMain(Screen, HelpableScreen):

# Create the helptext as a class variable
# This will be used as the basis for translations into other
# destination languages and the result will be kept for re-use
#
    helptext = {}
    base_helptext = """
Inside Plugin:
Left <-> Right : <-> +- EPG Event
Ok : enter text to translate
Bouquet : +- Zap
Menu : Setup
Blue: Hide screen
Yellow: Clear cache
Red: Refresh EPG
Back: Toggle primary/alternate language
"""
# Add the English (base) helptext now
#
    helptext['en'] = base_helptext.strip()

# ==================================================================
    def __init__(self, session, text):
        self.showsource = CfgPlTr.showsource.getValue()
        if self.showsource == "yes":
            size = MySD.tmyes
        else:
            size = MySD.tmno

        self.dict = {'size': size, 'plug_loc': plugin_location}
        self.skin = applySkinVars(MySD.TranslatorMain_skin, self.dict)
        self.session = session
        Screen.__init__(self, session)
        HelpableScreen.__init__(self)

        self.text = text
        self.hideflag = True
        self.refresh = False
        self.max = 1
        self.count = 0
        self.list = []
        self.eventName = ''

        self['from_lang'] = Label('')
        self['to_lang'] = Label('')
        self['timing'] = Label('')
        self['u_title'] = Label('')
        self['u_descr'] = ScrollLabel('')
        self['l_title'] = Label('')
        self['l_descr'] = ScrollLabel('')

        if self.showsource != "yes":
            self['l_title'].hide()
            self['l_descr'].hide()

# 'showVirtualKeyboard' is actually the Text key.
# Activated by including 'VirtualKeyboardActions' in the context list to
# ActionMap.
#
        AMbindings = {
         'ok': (self.get_text, _("Access text translator")),
         'cancel': (self.exit, _("Close plugin")),
         'down': (self.down, _("Scroll translated text down")),
         'up': (self.up, _("Scroll translated text up")),
         'red': (self.getEPG, _("Refresh EPG")),
         'green': (self.showInfo, _("Show plugin info")),
         'yellow': (self.clear_cache, _("Clear cache")),
         'blue': (self.hideScreen, _("Hide screen")),
         'menu': (self.config, _("Access plugin setup")),
         'info': (self.showInfo, _("Show plugin info")),
         'back': (self.toggle_trans, _("Toggle language")),
        }

# We need to know whether we are playing a recording as, if so, we do
# NOT want to activate the service-changing keys, nor programme text
# changes.
# We also don't need to set-up a ServiceEventTracker for a recording, as
# the even can't occur.
# The playback state is also needed for getEPG(), so save it.
# Do NOT use:
#   self.session.nav.getCurrentlyPlayingServiceOrGroup().isPlayback()
# as that isPlayback() is Vix-specific. So just replicate the code here.
#
        self.inPlayBack = "0:0:0:0:0:0:0:0:0" in self.My_Sref().toCompareString()

# Add the channel name.
        wintitle = _('EPG Translator')
        try:
            cur_serv = self.My_Sref().getServiceName()
            wintitle += " - " + cur_serv
        except:
            pass
        self.setTitle(wintitle)

        if not self.inPlayBack:  # We can add in service-change keys
            AMbindings.update({
             'right': (self.rightDown, _("Next EPG event")),
             'left': (self.leftUp, _("Previous EPG event")),
             'zapdown': (self.zapDown, _("Zap down")),
             'zapup': (self.zapUp, _("Zap up")),
            }, description=_("EPG Translator Actions"))
# Also add the event tracker for changing service for not-in-Playback
# This means we can call getEPG() *after* the service changes, even
# if there may be a user prompt related to timeshift.
#
            self.__event_tracker = ServiceEventTracker(screen=self,
                  eventmap={iPlayableService.evTunedIn: self.__serviceTuned})

        self['actions'] = HelpableActionMap(self, ['EPGTranslatorActions'],
             AMbindings, -1)
        self.onLayoutFinish.append(self.onLayoutFinished)

# For newer skins...
#
        self["key_blue"] = StaticText(_("Hide"))
        self["key_yellow"] = StaticText(_("Clear cache"))
        self["key_red"] = StaticText(_("Refresh EPG"))
        self["key_green"] = StaticText(_("Info"))
# Should create Menu and Back buttons here and use them....
# Also, can we fit in the OK button??? Move the clock somewhere else?
#
        self["key_ok"] = StaticText(_('Text input'))
        self["key_back"] = StaticText(_('Toggle language'))
        self["key_menu"] = StaticText(_('MENU'))


# ==================================================================
# Set the current country flags as the screen displays
#

    def onLayoutFinished(self):
        source = CfgPlTr.source.getValue()
        if source == "auto":
            source = _("Original")
        if self.showsource == 'yes':
            self['from_lang'].setText(source)
            dest_w = 'to_lang'
        else:
            dest_w = 'from_lang'
        self[dest_w].setText(get_lang(curr_dest))

# I think self.text is always None, but leave this here anyway.
        if self.text is None:
            self.getEPG()
        else:
            self.translateEPG(self.text, '')
        return

# ==================================================================
# When the service changes, get the EPG for it.
# And update the channel name.
#
    def __serviceTuned(self):
        wintitle = _('EPG Translator')
        try:
            cur_serv = self.My_Sref().getServiceName()
            wintitle += " - " + cur_serv
        except:
            pass
        self.setTitle(wintitle)
        self.getEPG()

# ==================================================================
# Get the ServiceRef for the current object
# We do this in several places
#
    def My_Sref(self):
        service = self.session.nav.getCurrentService()
        info = service.info()
        return eServiceReference(info.getInfoString(iServiceInformation.sServiceref))

# ==================================================================
# Bound to OK key. Request text (via a VirtualKeyBoard) to translate.
#
    def get_text(self):
        self.session.openWithCallback(self.translateText, VirtualKeyBoard, title=_('Text Translator:'), text='')

# ==================================================================
# Clear the cache of all items
#
    def clear_cache(self):
        AfCache.purge()
        self.session.open(MessageBox, _('Cache cleared'), MessageBox.TYPE_INFO, close_on_any_key=True)

# For both translate* calls we strip() any text we are given (consistency)

# ==================================================================
# Translate the text (entered via a VirtualKeyboard)
# and display it
#
    def translateText(self, text):
        if not text or text == '':      # Don't translate nothing
            return

        text = text.strip()
        self.setTitle('Text Translator')
# Set the time field to something useful.
# It is just a text label.
#
        self['timing'].setText(_("On-line translation"))
        newtext = DO_translation(text, CfgPlTr.source.getValue(), curr_dest)

        self['u_title'].setText("")
        self['l_title'].setText("")
        if self.showsource == 'yes':
            self['u_descr'].setText(text)
            self['l_descr'].setText(newtext)
        else:
            self['u_descr'].setText(newtext)
            self['l_descr'].setText("")

# ==================================================================
# Translate the text of an EPG description
# and display it
#
    def translateEPG(self, title, descr, do_translate=True):

        if title is None:
            title = ''
        else:
            title = title.strip()
        if descr is None:
            descr = ''
        else:
            descr = descr.strip()
        if (title == '') and (descr == ''):  # Don't display nothing
            return

# We might not have set epg_B for a recording, so this will drop to the
# exception. Also, add begin/duration spacing newlines here, so there
# are none if we hit the exception.
#
        try:
            begin = time.strftime("%a %Y-%m-%d %H:%M", time.localtime(int(self.event[epg_B])))
        except:
            begin = ''
        if self.event[epg_D] > 0:
            plen = (int(self.event[epg_D]) / 60)    # mins
            if plen >= 60:
                hr = int(plen / 60)
                plen -= 60 * hr
                duration = "%dh %dm" % (hr, plen)
            else:
                duration = "%dm" % (plen)
        else:
            duration = ''
        if do_translate:
# Check whether we already have the translation.
#
# If we are playing back a recording we'll have set epg_I to its path
# file_info and epg_N to the title, or "Recording"
#
            uref = make_uref(self.event[epg_I], self.event[epg_N])
            (t_title, t_descr) = AfCache.fetch(uref)
            if t_descr is None:  # Not there...
                try:
                    start = self.event[epg_PB]
                except:
                    start = self.event[epg_B]
                (t_title, t_descr) = EPGdata_translate(title, descr,
                     start, self.event[epg_D], uref)

# We now have the title+descr and t_title+t_descr to display
# None of the fields should have trailing newlines, so we should know
# where we are.
#
# begin + duration is always shown untranslated in its own field
#
        self['timing'].setText(begin + " - " + duration)
        if self.showsource == 'yes':
            self['u_title'].setText(title)
            self['u_descr'].setText(descr)
            self['l_title'].setText(t_title)
            self['l_descr'].setText(t_descr)
        else:
            self['u_title'].setText(t_title)
            self['u_descr'].setText(t_descr)
            self['l_title'].setText("")
            self['l_descr'].setText("")


# ==================================================================
# Populate the EPG data in self.list from the box's internal EPG cache
#

    def getEPG(self):
        self.max = 1
        self.count = 0      # Starting point in list
        self.list = []

# If we are in playback then there is no EPG cache related to it
# But some fields are still valid/consistent for an individual recording.
#
        if self.inPlayBack:
            ssn = self.session.nav
            service = ssn.getCurrentService()
            info = service.info()
            curEvent = info.getEvent(0)     # 0 == NOW, 1 == NEXT

# A downloaded file (from iPlayer - any mp4?) appears to have no
# curEvent, so cater for this.
# Set some default fields in case we fail for any reason...
#
            enedID = None
            short = ""
            extended = "Description unavailable"
            ename = "Unknown title"
            Servname = "Recording"
            dur = 0
            rec_began = None
            play_began = None
            if curEvent:
                try:
                    eventID = curEvent.getEventId()
                except:
                    pass
                try:
                    short = curEvent.getShortDescription()
                except:
                    pass
                try:
                    extended = curEvent.getExtendedDescription()
                except:
                    pass
                try:
                    ename = curEvent.getEventName()
                except:
                    pass
                Servname = ename
                try:
                    dur = curEvent.getDuration()
                except:
                    pass
# Approximate start time of playback
# The getPlayPosition is in units of 1/90000s
# BUT a playback has TWO start times.
#   The start of the original recording (-> epg_B)
#   The start of the playback (needed for cacheing timeout)
#
                try:
                    seek = service.seek()
                    secs_in = seek.getPlayPosition()[1] / 90000
                    play_began = int(time.time() - secs_in)
                except:
                    pass
                try:
                    rec_began = curEvent.getBeginTime()
                except:
                    pass

            if eventID is None:
# Generate another unique ID instead.
                try:
                    path = ssn.getCurrentlyPlayingServiceOrGroup().getPath()
                    finfo = os.stat(path)
                    eventID = str(finfo.st_dev) + ":" + str(finfo.st_ino)
                except:
                    eventID = str(int(time.time()))

# Create a list of the correct size with all elements None
#
            pbinfo = [None] * (len(EPG_OPTIONS) - 1)    # Ignoring X
            pbinfo[epg_I] = eventID
            pbinfo[epg_S] = short
            pbinfo[epg_E] = extended
            pbinfo[epg_T] = ename
            pbinfo[epg_N] = Servname
            pbinfo[epg_D] = dur
            pbinfo[epg_B] = rec_began
            if play_began is not None:
                pbinfo.append(play_began)   # epg_PB - and extra
            self.list = [tuple(pbinfo)]
        else:
# We'll get the same EPG (for the current channel) as would be displayed
# So we start at config.epg.histminutes before now.
# We'll remember everything returned by lookupEvent()
#
            t_now = int(time.time())
            epg_base = t_now - 60 * int(config.epg.histminutes.getValue())
            epg_extent = 1440 * 14    # Get up to 14 days from now (minutes)
            test = [EPG_OPTIONS, (self.My_Sref().toCompareString(), 0, epg_base, epg_extent)]
            epgcache = eEPGCache.getInstance()
            self.list = epgcache.lookupEvent(test)
            self.max = len(self.list)
# Update the starting point to the currently running service, which will be
# the last one before one with a future starting time
#
            for i in list(range(1, len(self.list))):
                if self.list[i][epg_B] > t_now:
                    break
                self.count = i
# Get the display going...
        self.showEPG()
        return

# ==================================================================
# Get the text and translate it for display
#
    def showEPG(self):
        try:
            self.event = self.list[self.count]
            title = self.event[epg_T]
            short = self.event[epg_S]
            extended = self.event[epg_E]
            self.refresh = False
        except:
            title = 'Press red button to refresh EPG'
            short = ''
            extended = ''
            self.refresh = True

# This MUST match the code in EventViewBase.setEvent() to get extended
# That way we can use the same cache for both...
#
        if short == title:
            short = ""
        if short and extended:
            extended = short + '\n' + extended
        elif short:
            extended = short
        self.translateEPG(title, extended)

# ==================================================================
    def leftUp(self):
        self.count -= 1
# Don't wrap....
        if self.count == -1:
            self.count = 0
        self.showEPG()

# ==================================================================
    def rightDown(self):
        self.count += 1
# Don't wrap....
        if self.count == self.max:
            self.count = self.max - 1
        self.showEPG()

# ==================================================================
    def up(self):
        self['u_descr'].pageUp()
        self['l_descr'].pageUp()

# ==================================================================
    def down(self):
        self['u_descr'].pageDown()
        self['l_descr'].pageDown()

# ==================================================================
    def zapUp(self):
        if InfoBar and InfoBar.instance:
            InfoBar.zapUp(InfoBar.instance)

# ==================================================================
    def zapDown(self):
        if InfoBar and InfoBar.instance:
            InfoBar.zapDown(InfoBar.instance)

# ==================================================================
    def showInfo(self):
# Display the help in the destination language
# Use our translation code to get this from the English if required.
#
        e2_lang = language.getActiveLanguage().split('_')[0]
        if e2_lang not in self.helptext:
            self.helptext[e2_lang] = DO_translation(self.helptext['en'], 'en', e2_lang)
        text = _("EPG Translator version: ") + EPGTrans_vers + "\n\n" + self.helptext[e2_lang]
        self.session.open(MessageBox, text, MessageBox.TYPE_INFO, close_on_any_key=True)

# ==================================================================
    def toggle_trans(self):

        global curr_dest
        if curr_dest == CfgPlTr.destination.getValue():
            curr_dest = CfgPlTr.alternate.getValue()
        else:
            curr_dest = CfgPlTr.destination.getValue()
        if self.showsource == 'yes':
            dest_w = 'to_lang'
        else:
            dest_w = 'from_lang'
        self[dest_w].setText(get_lang(curr_dest))
        self.showEPG()

# ==================================================================
    def config(self):
        self.session.openWithCallback(self.exit, TranslatorConfig)

# ==================================================================
    def hideScreen(self):
        with open('/proc/stb/video/alpha', 'w') as f:
            count = 40
            while count >= 0:
                if self.hideflag:
                    wv = count      # 40 -> 0
                else:
                    wv = 40 - count  # 0 -> 40
                f.write('%i' % (config.av.osd_alpha.getValue() * wv / 40))
                f.flush()               # So it does something
                count -= 1
        self.hideflag = not self.hideflag

# ==================================================================
    def exit(self):
        if self.hideflag is False:
            with open('/proc/stb/video/alpha', 'w') as f:
                f.write('%i' % config.av.osd_alpha.getValue())
        self.close()

# -*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-
# Code to link into EventView windows to allow them to be translated by
# pressing the Text key.
#


##################################################################
# The original values of functions we intercept
#
orig_EVB__init__ = None
orig_EVB_setEvent = None

# ==================================================================
# Code to toggle whether we are translating.
# Bound to Text in any EventView screen.
#


def EPGTr_ToggleMode(self):
    self.EPGTr_translating = not self.EPGTr_translating

# We need to update the event text - its translation state has changed.
# So we set the event to the current event.
# So we call setEvent(), which should now be My_setEvent() but we still
# call setEvent() in case some other plugin has intercepted the call as
# well.
#
    self.setEvent(self.event)

# ==================================================================


def EPGTr_ToggleView(self):
    global curr_dest
    if curr_dest == CfgPlTr.destination.getValue():
        curr_dest = CfgPlTr.alternate.getValue()
    else:
        curr_dest = CfgPlTr.destination.getValue()
    self.setEvent(self.event)

# ==================================================================
# The code to handle the text that will be displayed.
# This is an extension to the EventViewbase.setEvent().
#


def My_setEvent(self, event):
    global orig_EVB_setEvent

# First, call the original code
#
    orig_EVB_setEvent(self, event)

# If we aren't translating then we have nothing more to do...
#
    if not self.EPGTr_translating:
        return

# ... but if we are translating we need to change the text which
# the orig_EVB_setEvent() call above has set.
# As long as there is an event...
#
    if event is None or not hasattr(event, 'getEventName'):
        return

# Do we already have the translation for this lang/eventID/Service?
# If so, just use what we already have.
# NOTE that a playback of a programme with no Info (e.g. an Iplayer
# download) won't get here (since no EventView window appears).
# A playback of a recording will, and has valid getEventId() and
# getServiceName() results.
#
    uref = make_uref(event.getEventId(), self.currentService.getServiceName())
    (t_title, t_descr) = AfCache.fetch(uref)
    if t_descr is None:  # Not there...

# You may need to lookup in EventBase.setEvent to see how these fields
# are used and so how you can get the text to translate.
# On all distros (ATV PLi Vix eight):
#   o The current descr will have been put into the
#     self["FullDescription"] ScrollLabel object in all distros.
#   o The current title will have been set as the Title
#
# So get them from there and translate them
# Where the translations actually needs to be installed is
# version-dependent - see the end of this function.
#
        title = self.getTitle().strip()
        descr = self["FullDescription"].getText().strip()
        (t_title, t_descr) = EPGdata_translate(title, descr,
             event.getBeginTime(), event.getDuration(), uref)

# We have a set of translations now.
# Different skins use different fields for these data, so
# populate both for each.
#
# What needs to be set is distro-dependent
#
#    self["what"]            set to              distro
#   epg_description         title + extended    All
#   epg_eventname           title               Vix, PLi
#   summary_description     extended            Vix
#   FullDescription         extended            All
#   setTitle()              title               All
#
# If the right-to-left handling of the source and destination differ
# prepending a newline to the description seems to help.
#
    if (curr_dest in rtol) != (CfgPlTr.source.getValue() in rtol):
        sep = "\n"
        t_descr = "\n" + t_descr
    else:
        sep = "\n\n"

    if "epg_description" in self:
        self["epg_description"].setText(t_title + sep + t_descr)
    if "epg_eventname" in self:
        self["epg_eventname"].setText(t_title)
    if "summary_description" in self:
        self["summary_description"].setText(t_descr)
    if "FullDescription" in self:
        self["FullDescription"].setText(t_descr)
    self.setTitle(t_title)

# ==================================================================
# Intercepting code for EventViewBase __init__()
# We add an ActionMap for text key binding.
#


def My_EVB__init__(self, *args, **kwargs):
    global orig_EVB__init__

# First, call the original code
#
    orig_EVB__init__(self, *args, **kwargs)

# Add the bits to get a Text key handler for EventViewBase
# We create our own ActionMap. The VirtualKeyboardActions contexts only
# defines a Text key (convenient!) and calls it "showVirtualKeyboard".
#
    which = "EPGTrans"
    self[which] = ActionMap(["EventViewActions"], {
        "text": self.EPGTr_ToggleMode,
        "back": self.EPGTr_ToggleView})
    self[which].setEnabled(True)
    self["key_text"] = StaticText(_("Toggle translation"))
    self["key_back"] = StaticText(_("Toggle language"))

# Start each EventView in the user-chosen translate mode
#
    self.EPGTr_translating = CfgPlTr.start_EV_trans.getValue()


# ==================================================================
# Start-up links (see PluginDescriptor defs)
# This gets the current setting of functions we intercept
# (EventViewBase.__init__ EventViewBase.setEvent)
# and saves them (so they may be called by our interceptor) and replaces
# them with my "added-handler".
# We also add our additional handlers to EventViewBase
#
autostart_init_done = False


def autostart(reason, **kwargs):
    global orig_EVB__init__, orig_EVB_setEvent
    global autostart_init_done      # Otherwise we create a local one

# We only want to do this when starting (reason == 0)
# AND we only want to do it once (although we will probably only get
# called once with reason 0).

    if reason != 0:
        return
    if autostart_init_done:
        return

# Note that we will have done it.
#
    autostart_init_done = True

# Intercepted for additional code
#
    orig_EVB__init__ = EventViewBase.__init__
    EventViewBase.__init__ = My_EVB__init__
    orig_EVB_setEvent = EventViewBase.setEvent
    EventViewBase.setEvent = My_setEvent

# Added methods
#
    EventViewBase.EPGTr_ToggleMode = EPGTr_ToggleMode
    EventViewBase.EPGTr_ToggleView = EPGTr_ToggleView


# ==================================================================
# Where the Plugin starts when invoked via Plugins
#
def main(session, **kwargs):
    session.open(TranslatorMain, None)
    return

# ==================================================================


def Plugins(**kwargs):
    return [
     PluginDescriptor(name=_('EPG Translator'), description=_('Translate your EPG'), where=[PluginDescriptor.WHERE_PLUGINMENU], icon='plugin.png', fnc=main),
     PluginDescriptor(name=_('EPG Translator'), description=_('Translate your EPG'), where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main),
     PluginDescriptor(name=_('EPG Translator'), description=_('Translate your EPG'), where=[PluginDescriptor.WHERE_EVENTINFO], fnc=main),
     PluginDescriptor(name=_('EPG Translator'), description=_('Translate your EPG'), where=[PluginDescriptor.WHERE_AUTOSTART], fnc=autostart)
    ]
