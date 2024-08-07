# for localized messages
from . import _

from Components.ActionMap import ActionMap
from Components.Sensors import sensors
from Components.Sources.Sensor import SensorSource
from Components.Sources.StaticText import StaticText
from Components.ConfigList import ConfigListScreen
from Components.config import getConfigListEntry

from Screens.Screen import Screen

from Plugins.Plugin import PluginDescriptor
from Components.FanControl import fancontrol

try:
	from Components.SystemInfo import BoxInfo
	IMAGEDISTRO = BoxInfo.getItem("distro")
	BRAND = BoxInfo.getItem("brand")
except:
	from boxbranding import getImageDistro, getBrandOEM
	IMAGEDISTRO = getImageDistro()
	BRAND = getBrandOEM()


class TempFanControl(ConfigListScreen, Screen):
	skin = """
		<screen position="center,center" size="570,420" title="Fan Control" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="140,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="280,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="420,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />

			<widget name="config" position="10,50" size="550,120" scrollbarMode="showOnDemand" />

			<widget source="SensorTempText0" render="Label" position="10,150" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp0" render="Label" position="100,150" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText1" render="Label" position="10,170" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp1" render="Label" position="100,170" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText2" render="Label" position="10,190" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp2" render="Label" position="100,190" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText3" render="Label" position="10,210" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp3" render="Label" position="100,210" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText4" render="Label" position="10,230" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp4" render="Label" position="100,230" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText5" render="Label" position="10,250" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp5" render="Label" position="100,250" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText6" render="Label" position="10,270" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp6" render="Label" position="100,270" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorTempText7" render="Label" position="10,290" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorTemp7" render="Label" position="100,290" zPosition="1" size="100,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>

			<widget source="SensorFanText0" render="Label" position="290,150" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan0" render="Label" position="380,150" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText1" render="Label" position="290,170" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan1" render="Label" position="380,170" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText2" render="Label" position="290,190" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan2" render="Label" position="380,190" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText3" render="Label" position="290,210" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan3" render="Label" position="380,210" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText4" render="Label" position="290,230" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan4" render="Label" position="380,230" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText5" render="Label" position="290,250" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan5" render="Label" position="380,250" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText6" render="Label" position="290,270" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan6" render="Label" position="380,270" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
			<widget source="SensorFanText7" render="Label" position="290,290" zPosition="1" size="90,40" font="Regular;20" halign="left" valign="top" backgroundColor="#9f1313" transparent="1" />
			<widget source="SensorFan7" render="Label" position="380,290" zPosition="1" size="150,20" font="Regular;19" halign="right">
				<convert type="SensorToText"></convert>
			</widget>
		</screen>"""

	def __init__(self, session, args=None):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Fan Control"))

		templist = sensors.getSensorsList(sensors.TYPE_TEMPERATURE)
		tempcount = len(templist)
		fanlist = sensors.getSensorsList(sensors.TYPE_FAN_RPM)
		fancount = len(fanlist)

		self["key_red"] = self["red"] = StaticText(_("Cancel"))
		self["key_green"] = self["green"] = StaticText(_("OK"))

		for count in range(8):
			if count < tempcount:
				id = templist[count]
				if BRAND not in ('dags', 'vuplus'):
					self["SensorTempText%d" % count] = StaticText(sensors.getSensorName(id))
					self["SensorTemp%d" % count] = SensorSource(sensorid=id)
				elif BRAND in ('dags', 'vuplus') and id < 1:
					self["SensorTempText%d" % count] = StaticText(sensors.getSensorName(id))
					self["SensorTemp%d" % count] = SensorSource(sensorid=id)
				else:
					self["SensorTempText%d" % count] = StaticText("")
					self["SensorTemp%d" % count] = SensorSource()
			else:
				self["SensorTempText%d" % count] = StaticText("")
				self["SensorTemp%d" % count] = SensorSource()

			if count < fancount:
				id = fanlist[count]
				self["SensorFanText%d" % count] = StaticText(sensors.getSensorName(id))
				self["SensorFan%d" % count] = SensorSource(sensorid=id)
			else:
				self["SensorFanText%d" % count] = StaticText("")
				self["SensorFan%d" % count] = SensorSource()

		self.list = []
		for count in range(fancontrol.getFanCount()):
			if BRAND not in ('dags', 'vuplus'):
				self.list.append(getConfigListEntry(_("Fan %d voltage") % (count + 1), fancontrol.getConfig(count).vlt))
			self.list.append(getConfigListEntry(_("Fan %d PWM") % (count + 1), fancontrol.getConfig(count).pwm))
			if BRAND not in ('dags', 'vuplus'):
				self.list.append(getConfigListEntry(_("Standby fan %d voltage") % (count + 1), fancontrol.getConfig(count).vlt_standby))
			self.list.append(getConfigListEntry(_("Standby fan %d PWM") % (count + 1), fancontrol.getConfig(count).pwm_standby))

		ConfigListScreen.__init__(self, self.list, session=self.session)
		#self["config"].list = self.list
		#self["config"].setList(self.list)
		self["config"].l.setSeperation(300)

		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "MenuActions"],
		{
			"ok": self.save,
			"cancel": self.revert,
			"red": self.revert,
			"green": self.save,
			"menu": self.closeRecursive,
		}, -1)

	def save(self):
		for count in range(fancontrol.getFanCount()):
			if BRAND not in ('dags', 'vuplus'):
				fancontrol.getConfig(count).vlt.save()
			fancontrol.getConfig(count).pwm.save()
			if BRAND not in ('dags', 'vuplus'):
				fancontrol.getConfig(count).vlt_standby.save()
			fancontrol.getConfig(count).pwm_standby.save()
		self.close()

	def revert(self):
		for count in range(fancontrol.getFanCount()):
			if BRAND not in ('dags', 'vuplus'):
				fancontrol.getConfig(count).vlt.load()
			fancontrol.getConfig(count).pwm.load()
			if BRAND not in ('dags', 'vuplus'):
				fancontrol.getConfig(count).vlt_standby.load()
			fancontrol.getConfig(count).pwm_standby.load()
		self.close()


def main(session, **kwargs):
	session.open(TempFanControl)


def startMenu(menuid):
	if IMAGEDISTRO in ('openatv'):
		if menuid != "extended":
			return []
	elif IMAGEDISTRO in ('openhdf'):
		if menuid != "devices_menu":
			return []
	else:
		if menuid != "system":
			return []
	return [(_("Temperature and fan control"), main, "tempfancontrol", 80)]


def Plugins(**kwargs):
	from os import path
	if not path.exists("/usr/lib/enigma2/python/Plugins/Extensions/FanControl2/plugin.pyo"):
		return PluginDescriptor(name=_("Fan Control"), description=_("Temperature and Fan control"), where=PluginDescriptor.WHERE_MENU, needsRestart=False, fnc=startMenu)
	return []
