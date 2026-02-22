import adsk.core
import adsk.fusion
import traceback

import os
import sys
sys.path.append(os.path.dirname(__file__))
from BMLib import (
    genFrontPoints,
    genBackPoints,
    genLeftPoints,
    genRightPoints,
    genBottomPoints,
    genTopPoints,
)

# global set of event handlers to keep them referenced for the duration of the command
handlers = []

app = adsk.core.Application.get()
if app:
    ui = app.userInterface

DEFAULT_WIDTH = '500 mm'
DEFAULT_HEIGHT = '300 mm'
DEFAULT_DEPTH = '400 mm'
DEFAULT_THICKNESS = '6 mm'
DEFAULT_COMPONENT = app.activeProduct.rootComponent




def buildAll(component, w, h, d, thickness):
    buildFront(component, w, h, d, thickness)
    buildBack(component, w, h, d, thickness)
    buildLeft(component, w, h, d, thickness)
    buildRight(component, w, h, d, thickness)
    buildBottom(component, w, h, d, thickness)
    buildTop(component, w, h, d, thickness)


def buildFront(component, w, h, d, thickness):
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketchPoints(sketch, genFrontPoints(w, h, d, thickness))
    e = extrudeSketch(component, sketch, thickness)
    e.faces[0].body.name = "Front"
    moveExt(component, e, 'z', d - thickness)


def buildBack(component, w, h, d, thickness):
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketchPoints(sketch, genBackPoints(w, h, d, thickness))
    e = extrudeSketch(component, sketch, thickness)
    e.faces[0].body.name = "Back"


def buildLeft(component, w, h, d, thickness):
    sketch = component.sketches.add(component.yZConstructionPlane)
    sketchPoints(sketch, genLeftPoints(w, h, d, thickness))
    e = extrudeSketch(component, sketch, thickness)
    e.faces[0].body.name = "Left"


def buildRight(component, w, h, d, thickness):
    sketch = component.sketches.add(component.yZConstructionPlane)
    sketchPoints(sketch, genRightPoints(w, h, d, thickness))
    e = extrudeSketch(component, sketch, thickness)
    e.faces[0].body.name = "Right"
    moveExt(component, e, 'x', w - thickness)


def buildBottom(component, w, h, d, thickness):
    sketch = component.sketches.add(component.xZConstructionPlane)
    sketchPoints(sketch, genBottomPoints(w, h, d, thickness))
    e = extrudeSketch(component, sketch, thickness)
    e.faces[0].body.name = "Bottom"


def buildTop(component, w, h, d, thickness):
    sketch = component.sketches.add(component.xZConstructionPlane)
    sketchPoints(sketch, genTopPoints(w, h, d, thickness))
    e = extrudeSketch(component, sketch, thickness)
    e.faces[0].body.name = "Top"
    moveExt(component, e, 'y', h - thickness)


def moveExt(component, ext, axis, distance):
    if axis not in ('x', 'y', 'z'):
        raise ValueError("Axis must be one of x, y, z.")

    entities1 = adsk.core.ObjectCollection.create()
    entities1.add(ext.bodies.item(0))

    # Create a transform to do move
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(
        distance if axis == 'x' else 0.0,
        distance if axis == 'y' else 0.0,
        distance if axis == 'z' else 0.0,
    )

    # Create a move feature
    moveFeats = component.features.moveFeatures
    moveFeatureInput = moveFeats.createInput(entities1, transform)
    moveFeats.add(moveFeatureInput)


def sketchPoints(sketch, points):
    lines = sketch.sketchCurves.sketchLines
    points = list(points)

    lastX, lastY = points[-1]
    for (x, y) in points:
        lines.addByTwoPoints(
            adsk.core.Point3D.create(lastX, lastY, 0),
            adsk.core.Point3D.create(x, y, 0),
        )
        lastX, lastY = x, y


def extrudeSketch(component, sketch, thickness):
    # Get the profile defined by item#0.
    prof = sketch.profiles.item(0)

    # Create an extrusion feature
    extrudes = component.features.extrudeFeatures
    extInput = extrudes.createInput(
        prof,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )

    # Define the extrude distance based on thickness
    distance = adsk.core.ValueInput.createByReal(thickness)
    extInput.setDistanceExtent(False, distance)

    # Create the extrusion.
    return extrudes.add(extInput)


class BoxMakerCommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command = args.firingEvent.sender

            inputs = {}
            for input in command.commandInputs:
                inputs[input.id] = input

            # Ensure all inputs were provided
            requiredInputs = ['widthInput', 'heightInput', 'depthInput', 'thicknessInput']
            missingInputs = set(requiredInputs) - set(inputs.keys())
            if missingInputs:
                ui.messageBox("Missing inputs: {}".format(missingInputs))
                return

            # Get current design
            design = app.activeProduct
            if not design:
                ui.messageBox('No active Fusion design', 'No Design')
                return

            if not inputs['componentInput'].value == '':    
                # Get the root component of the active design
                rootComp = DEFAULT_COMPONENT

                allOccs = rootComp.occurrences
                transform = adsk.core.Matrix3D.create()

                # Create a component under root component
                occ1 = allOccs.addNewComponent(transform)
                occ1.component.name = inputs['componentInput'].value
                component=occ1.component
            else:
                component = DEFAULT_COMPONENT

            # Built it!
            buildAll(
                component,
                unitsMgr.evaluateExpression(inputs['widthInput'].expression, "mm"),
                unitsMgr.evaluateExpression(inputs['heightInput'].expression, "mm"),
                unitsMgr.evaluateExpression(inputs['depthInput'].expression, "mm"),
                unitsMgr.evaluateExpression(inputs['thicknessInput'].expression, "mm")
            )

            args.isValidResult = True

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BoxMakerCommandDestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BoxMakerCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command

            onExecute = BoxMakerCommandExecuteHandler()
            onDestroy = BoxMakerCommandDestroyHandler()
            cmd.execute.add(onExecute)
            cmd.destroy.add(onDestroy)

            # keep the handler referenced globally
            handlers.append(onExecute)
            handlers.append(onDestroy)

            cmd.commandInputs.addValueInput(
                'widthInput',
                'Width (mm)',
                'mm',
                adsk.core.ValueInput.createByString(DEFAULT_WIDTH)
            )

            cmd.commandInputs.addValueInput(
                'heightInput',
                'Height (mm)',
                'mm',
                adsk.core.ValueInput.createByString(DEFAULT_HEIGHT)
            )

            cmd.commandInputs.addValueInput(
                'depthInput',
                'Depth (mm)',
                'mm',
                adsk.core.ValueInput.createByString(DEFAULT_DEPTH)
            )

            cmd.commandInputs.addValueInput(
                'thicknessInput',
                'Wall Thickness',
                'mm',
                adsk.core.ValueInput.createByString(DEFAULT_THICKNESS)
            )

            cmd.commandInputs.addStringValueInput(
                'componentInput', 
                'Component,empty for root', 
                ''
            )

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def main():
    try:
        commandId = 'BoxMaker'
        commandName = 'BoxMaker'
        commandDescription = 'Create boxes with notched box-joint panels.'
        cmdDef = ui.commandDefinitions.itemById(commandId)
        if not cmdDef:
            cmdDef = ui.commandDefinitions.addButtonDefinition(
                commandId,
                commandName,
                commandDescription,
                './resources'
            )

        onCommandCreated = BoxMakerCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)

        # keep the handler referenced globally
        handlers.append(onCommandCreated)

        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminated when the script returns,
        # because we are waiting for event handlers to fire
        adsk.autoTerminate(False)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


main()
