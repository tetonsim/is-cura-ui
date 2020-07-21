import os
import io
import time
import json
import zipfile
import re
from string import Formatter
from typing import Dict, Tuple

import pywim
import threemf

from UM.PluginRegistry import PluginRegistry
from UM.Application import Application
from UM.Logger import Logger

from cura.Settings.ExtruderManager import ExtruderManager

from .requirements_tool.SmartSliceRequirements import SmartSliceRequirements
from .select_tool.SmartSliceSelectTool import SmartSliceSelectTool
from .SmartSlicePropertyHandler import SmartSlicePropertyHandler

from .utils import getPrintableNodes
from .utils import getModifierMeshes
from .utils import getNodeActiveExtruder
from .utils import findChildSceneNode
from .stage.SmartSliceScene import Root

"""
  SmartSliceJobHandler

    The Job Handler contains functionality for updating and checking Smart Slice jobs
    from the Cura meshes, slice settings, and requirements / use cases.

"""
class SmartSliceJobHandler:

    INFILL_CURA_SMARTSLICE = {
        "grid": pywim.am.InfillType.grid,
        "triangles": pywim.am.InfillType.triangle,
        #"cubic": pywim.am.InfillType.cubic
    }
    INFILL_SMARTSLICE_CURA = {value: key for key, value in INFILL_CURA_SMARTSLICE.items()}

    INFILL_DIRECTION = 45

    def __init__(self, handler: SmartSlicePropertyHandler):
        self._all_extruders_settings = None
        self._propertyHandler = handler

    # Builds and checks a smart slice job for errors based on current setup defined by the property handler
    # Will return the job, and a dictionary of error keys and associated error resolutions
    def checkJob(self, machine_name="printer") -> Tuple[pywim.smartslice.job.Job, Dict[str, str]]:

        if len(getPrintableNodes()) == 0:
            return None, {}

        # Create a new instance of errors. We will use this to replace the old errors and
        # emit a signal to replace them
        errors = []

        if len(getPrintableNodes()) != 1:
            errors.append(pywim.smartslice.val.InvalidSetup(
                "Invalid number of printable models on the build tray",
                "Only 1 printable model is currently supported"
            ))

        # We build a new job from scratch evertime - it's easier than trying to manage a whole bunch of changes
        job = pywim.smartslice.job.Job()

        # Extruder Manager
        extruderManager = Application.getInstance().getExtruderManager()
        emActive = extruderManager._active_extruder_index

        # Normal mesh
        normal_mesh = getPrintableNodes()[0]

        # Check the material
        machine_extruder = getNodeActiveExtruder(normal_mesh)
        guid = machine_extruder.material.getMetaData().get("GUID", "")
        material = self._getMaterial(guid)

        if not material:
            errors.append(pywim.smartslice.val.InvalidSetup(
                "Material <i>{}</i> is not currently characterized for Smart Slice".format(machine_extruder.material.name),
                "Please select a characterized material."
            ))
        else:
            job.bulk.add(
                pywim.fea.model.Material.from_dict(material)
            )

        # Get all nodes to cycle through
        nodes = [normal_mesh] + getModifierMeshes()


        # Cycle through all of the meshes and check extruder
        for node in nodes:
            active_extruder = getNodeActiveExtruder(node)

            # Build the data for Smart Slice error checking
            mesh = pywim.chop.mesh.Mesh(node.getName())
            mesh.print_config.aux = self._getAuxDict(node.callDecoration("getStack"))
            job.chop.meshes.add(mesh)

            # Check the active extruder
            any_individual_extruder = all(map(lambda k : (int(active_extruder.getProperty(k, "value")) <= 0), SmartSlicePropertyHandler.EXTRUDER_KEYS))
            if not ( int(active_extruder.getMetaDataEntry("position")) == 0 and int(emActive) == 0 and any_individual_extruder ):
                errors.append(pywim.smartslice.val.InvalidSetup(
                    "Invalid extruder selected for <i>{}</i>".format(node.getName()),
                    "Change active extruder to Extruder 1"
                ))

        # Use Cases
        smart_sliceScene_node = findChildSceneNode(getPrintableNodes()[0], Root)
        if smart_sliceScene_node:
            job.chop.steps = smart_sliceScene_node.createSteps()

        # Requirements
        req_tool = SmartSliceRequirements.getInstance()
        job.optimization.min_safety_factor = req_tool.targetSafetyFactor
        job.optimization.max_displacement = req_tool.maxDisplacement

        # Global print config -- assuming only 1 extruder is active for ALL meshes right now
        print_config = pywim.am.Config()
        print_config.layer_height = self._propertyHandler.getGlobalProperty("layer_height")
        print_config.layer_width = self._propertyHandler.getExtruderProperty("line_width")
        print_config.walls = self._propertyHandler.getExtruderProperty("wall_line_count")
        print_config.bottom_layers = self._propertyHandler.getExtruderProperty("top_layers")
        print_config.top_layers = self._propertyHandler.getExtruderProperty("bottom_layers")

        # > https://github.com/Ultimaker/CuraEngine/blob/master/src/FffGcodeWriter.cpp#L402
        skin_angles = self._propertyHandler.getExtruderProperty("skin_angles")
        if type(skin_angles) is str:
            skin_angles = eval(skin_angles)
        if len(skin_angles) > 0:
            print_config.skin_orientations.extend(tuple(skin_angles))
        else:
            print_config.skin_orientations.extend((45, 135))

        infill_pattern = self._propertyHandler.getExtruderProperty("infill_pattern")
        print_config.infill.density = self._propertyHandler.getExtruderProperty("infill_sparse_density")
        if infill_pattern in self.INFILL_CURA_SMARTSLICE.keys():
            print_config.infill.pattern = self.INFILL_CURA_SMARTSLICE[infill_pattern]
        else:
            print_config.infill.pattern = infill_pattern # The job validation will handle the error

        # > https://github.com/Ultimaker/CuraEngine/blob/master/src/FffGcodeWriter.cpp#L366
        infill_angles = self._propertyHandler.getExtruderProperty("infill_angles")
        if type(infill_angles) is str:
            infill_angles = eval(infill_angles)
        if not len(infill_angles):
            print_config.infill.orientation = self.INFILL_DIRECTION
        else:
            if len(infill_angles) > 1:
                Logger.log("w", "More than one infill angle is set! Only the first will be taken!")
                Logger.log("d", "Ignoring the angles: {}".format(infill_angles[1:]))
            print_config.infill.orientation = infill_angles[0]

        print_config.auxiliary = self._getAuxDict(
            Application.getInstance().getGlobalContainerStack()
        )

        # Extruder config
        extruders = ()
        machine_extruder = getNodeActiveExtruder(normal_mesh)
        for extruder_stack in [machine_extruder]:
            extruder = pywim.chop.machine.Extruder(diameter=extruder_stack.getProperty("machine_nozzle_size", "value"))
            extruder.print_config.auxiliary = self._getAuxDict(extruder_stack)
            extruders += (extruder,)

        printer = pywim.chop.machine.Printer(name=machine_name, extruders=extruders)
        job.chop.slicer = pywim.chop.slicer.CuraEngine(config=print_config, printer=printer)

        # Check the job and add the errors
        errors = errors + job.validate()

        error_dict = {}
        for err in errors:
            error_dict[err.error()] = err.resolution()

        return job, error_dict

    # Builds a complete smart slice job to be written to a 3MF
    def buildJobFor3mf(self, machine_name="printer") -> pywim.smartslice.job.Job:

        job, errors = self.checkJob(machine_name)

        # Clear out the data we don't need or will override
        job.chop.meshes.clear()
        job.extruders.clear()

        if len(errors) > 0:
            Logger.log("w", "Unresolved errors in the Smart Slice setup!")
            return None

        normal_mesh = getPrintableNodes()[0]

        # The am.Config contains an "auxiliary" dictionary which should
        # be used to define the slicer specific settings. These will be
        # passed on directly to the slicer (CuraEngine).
        print_config = job.chop.slicer.print_config
        print_config.auxiliary = self._buildGlobalSettingsMessage()

        # Setup the slicer configuration. See each class for more
        # information.
        extruders = ()
        machine_extruder = getNodeActiveExtruder(normal_mesh)
        for extruder_stack in [machine_extruder]:
            extruder_nr = extruder_stack.getProperty("extruder_nr", "value")
            extruder_object = pywim.chop.machine.Extruder(diameter=extruder_stack.getProperty("machine_nozzle_size", "value"))
            pickled_info = self._buildExtruderMessage(extruder_stack)
            extruder_object.id = pickled_info["id"]
            extruder_object.print_config.auxiliary = pickled_info["settings"]
            extruders += (extruder_object,)

            # Create the extruder object in the smart slice job that defines
            # the usable bulk materials for this extruder. Currently, all materials
            # are usable in each extruder (should only be one extruder right now).
            extruder_materials = pywim.smartslice.job.Extruder(number=extruder_nr)
            extruder_materials.usable_materials.extend(
                [m.name for m in job.bulk]
            )

            job.extruders.append(extruder_materials)

        if len(extruders) == 0:
            Logger.log("e", "Did not find the extruder with position %i", machine_extruder.position)

        printer = pywim.chop.machine.Printer(name=machine_name, extruders=extruders)

        # And finally set the slicer to the Cura Engine with the config and printer defined above
        job.chop.slicer = pywim.chop.slicer.CuraEngine(config=print_config, printer=printer)

        return job

    # Writes a smartslice job to a 3MF file
    @classmethod
    def write3mf(self, threemf_path, mesh_nodes, job: pywim.smartslice.job.Job):

        # Getting 3MF writer and write our file
        threeMF_Writer = PluginRegistry.getInstance().getPluginObject("3MFWriter")
        threeMF_Writer.write(threemf_path, mesh_nodes)

        threemf_file = zipfile.ZipFile(threemf_path, 'a')
        threemf_file.writestr('SmartSlice/job.json', job.to_json() )
        threemf_file.close()

        return True

    # Reads a 3MF file into a smartslice job
    @classmethod
    def extractSmartSliceJobFrom3MF(self, file) -> pywim.smartslice.job.Job:
        tmf = threemf.ThreeMF()

        tmf_reader = threemf.io.Reader()
        tmf_reader.register_extension(pywim.smartslice.ThreeMFExtension)

        tmf_reader.read(tmf, file)

        if len(tmf.extensions) != 1:
            raise Exception('3MF extension count is not 1')

        ext = tmf.extensions[0]

        job_assets = list(
            filter(lambda a: isinstance(a, pywim.smartslice.JobThreeMFAsset), ext.assets)
        )

        if len(job_assets) == 0:
            raise SmartSliceCloudJob.JobException('Could not find smart slice information in 3MF')

        return job_assets[0].content

    def _getMaterial(self, guid):
        this_dir = os.path.split(__file__)[0]
        database_location = os.path.join(this_dir, "data", "POC_material_database.json")
        jdata = json.loads(open(database_location).read())

        for material in jdata["materials"]:
            if "cura-guid" not in material.keys():
                continue
            if guid in material["cura-guid"]:
                return material

        return None

    def _getAuxDict(self, stack):
        aux = {}
        for prop in pywim.smartslice.val.NECESSARY_PRINT_PARAMETERS:
            val = stack.getProperty(prop, "value")
            if val:
                aux[prop] = str(val)

        return aux

    ##  Check if a node has per object settings and ensure that they are set correctly in the message
    #   \param node Node to check.
    #   \param message object_lists message to put the per object settings in
    def _handlePerObjectSettings(self, node):
        stack = node.callDecoration("getStack")

        # Check if the node has a stack attached to it and the stack has any settings in the top container.
        if not stack:
            return

        # Check all settings for relations, so we can also calculate the correct values for dependent settings.
        top_of_stack = stack.getTop()  # Cache for efficiency.
        changed_setting_keys = top_of_stack.getAllKeys()

        # Add all relations to changed settings as well.
        for key in top_of_stack.getAllKeys():
            instance = top_of_stack.getInstance(key)
            self._addRelations(changed_setting_keys, instance.definition.relations)

        # Ensure that the engine is aware what the build extruder is.
        changed_setting_keys.add("extruder_nr")

        settings = []
        # Get values for all changed settings
        for key in changed_setting_keys:
            setting = {}
            setting["name"] = key
            extruder = int(round(float(stack.getProperty(key, "limit_to_extruder"))))

            # Check if limited to a specific extruder, but not overridden by per-object settings.
            if extruder >= 0 and key not in changed_setting_keys:
                limited_stack = ExtruderManager.getInstance().getActiveExtruderStacks()[extruder]
            else:
                limited_stack = stack

            setting["value"] = str(limited_stack.getProperty(key, "value"))

            settings.append(setting)

        return settings

    def _cacheAllExtruderSettings(self):
        global_stack = Application.getInstance().getGlobalContainerStack()

        # NB: keys must be strings for the string formatter
        self._all_extruders_settings = {
            "-1": self._buildReplacementTokens(global_stack)
        }
        for extruder_stack in ExtruderManager.getInstance().getActiveExtruderStacks():
            extruder_nr = extruder_stack.getProperty("extruder_nr", "value")
            self._all_extruders_settings[str(extruder_nr)] = self._buildReplacementTokens(extruder_stack)

    # #  Creates a dictionary of tokens to replace in g-code pieces.
    #
    #   This indicates what should be replaced in the start and end g-codes.
    #   \param stack The stack to get the settings from to replace the tokens
    #   with.
    #   \return A dictionary of replacement tokens to the values they should be
    #   replaced with.
    def _buildReplacementTokens(self, stack):

        result = {}
        for key in stack.getAllKeys():
            value = stack.getProperty(key, "value")
            result[key] = value

        result["print_bed_temperature"] = result["material_bed_temperature"]  # Renamed settings.
        result["print_temperature"] = result["material_print_temperature"]
        result["travel_speed"] = result["speed_travel"]
        result["time"] = time.strftime("%H:%M:%S")  # Some extra settings.
        result["date"] = time.strftime("%d-%m-%Y")
        result["day"] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][int(time.strftime("%w"))]

        initial_extruder_stack = Application.getInstance().getExtruderManager().getUsedExtruderStacks()[0]
        initial_extruder_nr = initial_extruder_stack.getProperty("extruder_nr", "value")
        result["initial_extruder_nr"] = initial_extruder_nr

        return result

    # #  Replace setting tokens in a piece of g-code.
    #   \param value A piece of g-code to replace tokens in.
    #   \param default_extruder_nr Stack nr to use when no stack nr is specified, defaults to the global stack
    def _expandGcodeTokens(self, value, default_extruder_nr) -> str:
        self._cacheAllExtruderSettings()

        try:
            # any setting can be used as a token
            fmt = GcodeStartEndFormatter(default_extruder_nr=default_extruder_nr)
            if self._all_extruders_settings is None:
                return ""
            settings = self._all_extruders_settings.copy()
            settings["default_extruder_nr"] = default_extruder_nr
            return str(fmt.format(value, **settings))
        except:
            Logger.logException("w", "Unable to do token replacement on start/end g-code")
            return str(value)

    def _modifyInfillAnglesInSettingDict(self, settings):
        for key, value in settings.items():
            if key == "infill_angles":
                if type(value) is str:
                    value = eval(value)
                if len(value) is 0:
                    settings[key] = [self.INFILL_DIRECTION]
                else:
                    settings[key] = [value[0]]

        return settings

    # #  Sends all global settings to the engine.
    #
    #   The settings are taken from the global stack. This does not include any
    #   per-extruder settings or per-object settings.
    def _buildGlobalSettingsMessage(self, stack=None):
        if not stack:
            stack = Application.getInstance().getGlobalContainerStack()

        if not stack:
            return

        self._cacheAllExtruderSettings()

        if self._all_extruders_settings is None:
            return

        settings = self._all_extruders_settings["-1"].copy()

        # Pre-compute material material_bed_temp_prepend and material_print_temp_prepend
        start_gcode = settings["machine_start_gcode"]
        bed_temperature_settings = ["material_bed_temperature", "material_bed_temperature_layer_0"]
        pattern = r"\{(%s)(,\s?\w+)?\}" % "|".join(bed_temperature_settings)  # match {setting} as well as {setting, extruder_nr}
        settings["material_bed_temp_prepend"] = re.search(pattern, start_gcode) == None
        print_temperature_settings = ["material_print_temperature", "material_print_temperature_layer_0", "default_material_print_temperature", "material_initial_print_temperature", "material_final_print_temperature", "material_standby_temperature"]
        pattern = r"\{(%s)(,\s?\w+)?\}" % "|".join(print_temperature_settings)  # match {setting} as well as {setting, extruder_nr}
        settings["material_print_temp_prepend"] = re.search(pattern, start_gcode) == None

        # Replace the setting tokens in start and end g-code.
        # Use values from the first used extruder by default so we get the expected temperatures
        initial_extruder_stack = Application.getInstance().getExtruderManager().getUsedExtruderStacks()[0]
        initial_extruder_nr = initial_extruder_stack.getProperty("extruder_nr", "value")

        settings["machine_start_gcode"] = self._expandGcodeTokens(settings["machine_start_gcode"], initial_extruder_nr)
        settings["machine_end_gcode"] = self._expandGcodeTokens(settings["machine_end_gcode"], initial_extruder_nr)

        settings = self._modifyInfillAnglesInSettingDict(settings)

        for key, value in settings.items():
            if type(value) is not str:
                settings[key] = str(value)

        return settings

    # #  Sends for some settings which extruder they should fallback to if not
    #   set.
    #
    #   This is only set for settings that have the limit_to_extruder
    #   property.
    #
    #   \param stack The global stack with all settings, from which to read the
    #   limit_to_extruder property.
    def _buildGlobalInheritsStackMessage(self, stack):
        limit_to_extruder_message = []
        for key in stack.getAllKeys():
            extruder_position = int(round(float(stack.getProperty(key, "limit_to_extruder"))))
            if extruder_position >= 0:  # Set to a specific extruder.
                setting_extruder = {}
                setting_extruder["name"] = key
                setting_extruder["extruder"] = extruder_position
                limit_to_extruder_message.append(setting_extruder)
        return limit_to_extruder_message

    # #  Create extruder message from stack
    def _buildExtruderMessage(self, stack) -> dict:
        extruder_message = {}
        extruder_message["id"] = int(stack.getMetaDataEntry("position"))
        self._cacheAllExtruderSettings()

        if self._all_extruders_settings is None:
            return

        extruder_nr = stack.getProperty("extruder_nr", "value")
        settings = self._all_extruders_settings[str(extruder_nr)].copy()

        # Also send the material GUID. This is a setting in fdmprinter, but we have no interface for it.
        settings["material_guid"] = stack.material.getMetaDataEntry("GUID", "")

        # Replace the setting tokens in start and end g-code.
        extruder_nr = stack.getProperty("extruder_nr", "value")
        settings["machine_extruder_start_code"] = self._expandGcodeTokens(settings["machine_extruder_start_code"], extruder_nr)
        settings["machine_extruder_end_code"] = self._expandGcodeTokens(settings["machine_extruder_end_code"], extruder_nr)

        settings = self._modifyInfillAnglesInSettingDict(settings)

        for key, value in settings.items():
            if type(value) is not str:
                settings[key] = str(value)

        extruder_message["settings"] = settings

        return extruder_message

# #  Formatter class that handles token expansion in start/end gcode
class GcodeStartEndFormatter(Formatter):

    def __init__(self, default_extruder_nr: int=-1) -> None:
        super().__init__()
        self._default_extruder_nr = default_extruder_nr

    def get_value(self, key: str, args: str, kwargs: dict) -> str:  # type: ignore # [CodeStyle: get_value is an overridden function from the Formatter class]
        # The kwargs dictionary contains a dictionary for each stack (with a string of the extruder_nr as their key),
        # and a default_extruder_nr to use when no extruder_nr is specified

        extruder_nr = self._default_extruder_nr

        key_fragments = [fragment.strip() for fragment in key.split(",")]
        if len(key_fragments) == 2:
            try:
                extruder_nr = int(key_fragments[1])
            except ValueError:
                try:
                    extruder_nr = int(kwargs["-1"][key_fragments[1]])  # get extruder_nr values from the global stack #TODO: How can you ever provide the '-1' kwarg?
                except (KeyError, ValueError):
                    # either the key does not exist, or the value is not an int
                    Logger.log("w", "Unable to determine stack nr '%s' for key '%s' in start/end g-code, using global stack", key_fragments[1], key_fragments[0])
        elif len(key_fragments) != 1:
            Logger.log("w", "Incorrectly formatted placeholder '%s' in start/end g-code", key)
            return "{" + key + "}"

        key = key_fragments[0]

        default_value_str = "{" + key + "}"
        value = default_value_str
        # "-1" is global stack, and if the setting value exists in the global stack, use it as the fallback value.
        if key in kwargs["-1"]:
            value = kwargs["-1"][key]
        if str(extruder_nr) in kwargs and key in kwargs[str(extruder_nr)]:
            value = kwargs[str(extruder_nr)][key]

        if value == default_value_str:
            Logger.log("w", "Unable to replace '%s' placeholder in start/end g-code", key)

        return value
