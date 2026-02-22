#Author-Autodesk Inc.
#Description-Create a spur gear.

import adsk.core, adsk.fusion, traceback
import os, math

commandId = 'SpurGearCommandIdPy'

# global set of event handlers to keep them referenced for the duration of the command
handlers = []

def commandDefinitionById(id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    if not id:
        ui.messageBox('commandDefinition id is not specified')
        return None
    commandDefinitions_ = ui.commandDefinitions
    commandDefinition_ = commandDefinitions_.itemById(id)
    return commandDefinition_

def commandControlById(id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    if not id:
        ui.messageBox('commandControl id is not specified')
        return None
    workspaces_ = ui.workspaces
    modelingWorkspace_ = workspaces_.itemById('FusionSolidEnvironment')
    toolbarPanels_ = modelingWorkspace_.toolbarPanels
    toolbarPanel_ = toolbarPanels_.item(0)
    toolbarControls_ = toolbarPanel_.controls
    toolbarControl_ = toolbarControls_.itemById(id)
    return toolbarControl_

def destroyObject(uiObj, tobeDeleteObj):
    if uiObj and tobeDeleteObj:
        if tobeDeleteObj.isValid:
            tobeDeleteObj.deleteMe()
        else:
            uiObj.messageBox('tobeDeleteObj is not a valid object')

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        if app:
            ui = app.userInterface

        newComp = None

        def createNewComponent():
            # Get the active design.
            product = app.activeProduct
            design = adsk.fusion.Design.cast(product)
            rootComp = design.rootComponent
            allOccs = rootComp.occurrences
            newOcc = allOccs.addNewComponent(adsk.core.Matrix3D.create())
            return newOcc.component

        class SpurGearCommandExecuteHandler(adsk.core.CommandEventHandler):
            def __init__(self):
                super().__init__()
            def notify(self, args):
                try:
                    unitsMgr = app.activeProduct.unitsManager
                    command = args.firingEvent.sender
                    inputs = command.commandInputs

                    diaPitchInput = 0
                    pressureAngleInput = 0
                    numTeethInput = 0
                    thicknessInput = 0

                    # We need access to the inputs within a command during the execute.
                    for input in inputs:
                        if input.id == 'diaPitch':
                            diaPitchInput = input
                        elif input.id == 'pressureAngle':
                            pressureAngleInput = input
                        elif input.id == 'numTeeth':
                            numTeethInput = input
                        elif input.id == 'thickness':
                            thicknessInput = input

                    diaPitch = 0
                    pressureAngle = 0
                    numTeeth = 0
                    thickness = 0

                    if not diaPitchInput or not pressureAngleInput or not numTeethInput or not thicknessInput:
                        ui.messageBox("One of the inputs don't exist.")

                        diaPitch = 7.62
                        pressureAngle = 20.0 * (math.pi / 180)
                        numTeeth = 24
                        thickness = 3.5
                    else:
                        diaPitch = unitsMgr.evaluateExpression(diaPitchInput.expression, "cm")
                        pressureAngle = unitsMgr.evaluateExpression(pressureAngleInput.expression, "deg")
                        thickness = unitsMgr.evaluateExpression(thicknessInput.expression, "cm")

                        if numTeethInput.value == '':
                            numTeeth = 24
                        else:
                            numTeeth = int(numTeethInput.value)

                    buildGear(diaPitch, numTeeth, pressureAngle, thickness)

                except:
                    if ui:
                        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

        class SpurGearCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
            def __init__(self):
                super().__init__()
            def notify(self, args):
                try:
                    cmd = args.command
                    onExecute = SpurGearCommandExecuteHandler()
                    cmd.execute.add(onExecute)
                    # keep the handler referenced beyond this function
                    handlers.append(onExecute)

                    # Define the inputs.
                    inputs = cmd.commandInputs

                    initialVal = adsk.core.ValueInput.createByReal(7.62)
                    inputs.addValueInput('diaPitch', 'Diametral Pitch.', 'cm' , initialVal)

                    initialVal2 = adsk.core.ValueInput.createByReal(20.0 * (math.pi / 180))
                    inputs.addValueInput('pressureAngle', 'Pressure Angle', 'deg' , initialVal2)

                    inputs.addStringValueInput('numTeeth', 'Number of Teeth', '24')

                    initialVal4 = adsk.core.ValueInput.createByReal(2.0)
                    inputs.addValueInput('thickness', 'Gear Thickness', 'cm' , initialVal4)

                except:
                    if ui:
                        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

        # Calculate points along an involute curve.
        def involutePoint(baseCircleRadius, distFromCenterToInvolutePoint):
            l = math.sqrt(distFromCenterToInvolutePoint * distFromCenterToInvolutePoint - baseCircleRadius * baseCircleRadius)

            alpha = l / baseCircleRadius

            theta = alpha - math.acos(baseCircleRadius / distFromCenterToInvolutePoint)

            x = distFromCenterToInvolutePoint * math.cos(theta)
            y = distFromCenterToInvolutePoint * math.sin(theta)

            return adsk.core.Point3D.create(x, y, 0)

        def createExtrude(prof, thickness):
            global newComp
            extrudes = newComp.features.extrudeFeatures
            extInput = extrudes.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)

            distance = adsk.core.ValueInput.createByReal(thickness)
            extInput.setDistanceExtent(False, distance)
            return extrudes.add(extInput)

        def getCylinderFace(body):
            for face in body.faces:
                if face.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType:
                    return face

        # Construct a gear.
        def buildGear(diametralPitch, numTeeth, pressureAngle, thickness):
            global newComp
            newComp = createNewComponent()
            if newComp is None:
                ui.messageBox('New component failed to create', 'New Component Failed')
                return

            # Create a new sketch.
            sketches = newComp.sketches
            xyPlane = newComp.xYConstructionPlane
            sketch = sketches.add(xyPlane)

            # Compute the various values for a gear.
            pitchDia = numTeeth / diametralPitch
            if diametralPitch < (20 *(math.pi/180)):
                dedendum = 1.157 / diametralPitch 
            else:
                dedendum = 1.25 / diametralPitch

            rootDiameter = pitchDia - (2 * dedendum)
            baseCircleDiameter = pitchDia * math.cos(pressureAngle)
            outsideDia = (numTeeth + 2) / diametralPitch

            # Calculate points along the involute curve.
            involutePointCount = 10   
            involuteIntersectionRadius = baseCircleDiameter / 2.0
            involutePoints = []
            radiusStep = ((outsideDia - involuteIntersectionRadius * 2) / 2) / (involutePointCount - 1)
            for i in range(0, involutePointCount):
                newPoint = involutePoint(baseCircleDiameter / 2.0, involuteIntersectionRadius)
                involutePoints.append(newPoint)
                involuteIntersectionRadius = involuteIntersectionRadius + radiusStep

            # Determine the angle between the X axis and a line between the origin of the curve
            # and the intersection point between the involute and the pitch diameter circle.
            pitchInvolutePoint = involutePoint(baseCircleDiameter / 2.0, pitchDia / 2.0)
            pitchPointAngle = math.atan(pitchInvolutePoint.y / pitchInvolutePoint.x)

            # Determine the angle defined by the tooth thickness as measured at
            # the pitch diameter circle.
            tooththicknessAngle = -(2 * math.pi) / (2 * numTeeth)

            # Rotate the involute so the intersection point lies on the x axis.
            cosAngle = math.cos(-pitchPointAngle + (tooththicknessAngle / 2))
            sinAngle = math.sin(-pitchPointAngle + (tooththicknessAngle / 2))
            for i in range(0, involutePointCount):
                involutePoints[i].x = involutePoints[i].x * cosAngle - involutePoints[i].y * sinAngle
                involutePoints[i].y = involutePoints[i].x * sinAngle + involutePoints[i].y * cosAngle

            # Create a new set of points with a negated y.  This effectively mirrors the original
            # points about the X axis.
            involute2Points = []
            for i in range(0, involutePointCount):
                involute2Points.append(adsk.core.Point3D.create(involutePoints[i].x, -involutePoints[i].y, 0))

            curve1Dist = []
            curve1Angle = []
            for i in range(0, involutePointCount):
                curve1Dist.append(math.sqrt(involutePoints[i].x * involutePoints[i].x + involutePoints[i].y * involutePoints[i].y))
                curve1Angle.append(math.atan(involutePoints[i].y / involutePoints[i].x))

            curve2Dist = []
            curve2Angle = []
            for i in range(0, involutePointCount):
                curve2Dist.append(math.sqrt(involute2Points[i].x * involute2Points[i].x + involute2Points[i].y * involute2Points[i].y))
                curve2Angle.append(math.atan(involute2Points[i].y / involute2Points[i].x))

            sketch.isComputeDeferred = True
            angleDiff = -tooththicknessAngle * 2

            # Create and load an object collection with the points.
            pointSet = adsk.core.ObjectCollection.create()
            for i in range(0, involutePointCount):
                pointSet.add(involutePoints[i])

            # Create the first spline.
            spline1 = sketch.sketchCurves.sketchFittedSplines.add(pointSet)

            # Add the involute points for the second spline to an ObjectCollection.
            pointSet = adsk.core.ObjectCollection.create()
            for i in range(0, involutePointCount):
                pointSet.add(involute2Points[i])

            # Create the second spline.
            spline2 = sketch.sketchCurves.sketchFittedSplines.add(pointSet)

            currentAngle = 0

            if baseCircleDiameter >= rootDiameter:
                rootPoint1 = adsk.core.Point3D.create((rootDiameter / 2) * math.cos(curve1Angle[0] + currentAngle), (rootDiameter / 2) * math.sin(curve1Angle[0] + (currentAngle)), 0)
                sketch.sketchCurves.sketchLines.addByTwoPoints(rootPoint1, spline1.startSketchPoint)

                rootPoint2 = adsk.core.Point3D.create((rootDiameter / 2) * math.cos(curve2Angle[0] + (currentAngle)), (rootDiameter / 2) * math.sin(curve2Angle[0] + (currentAngle)), 0)
                sketch.sketchCurves.sketchLines.addByTwoPoints(rootPoint2, spline2.startSketchPoint)

            midPoint = adsk.core.Point3D.create((outsideDia / 2) * math.cos(currentAngle), (outsideDia / 2) * math.sin(currentAngle), 0)
            sketch.sketchCurves.sketchArcs.addByThreePoints(spline1.endSketchPoint, midPoint, spline2.endSketchPoint)

            currentAngle = angleDiff * 1

            # Rotate the involute points for the next tooth.
            for i in range(0, involutePointCount):
                involutePoints[i].x = curve1Dist[i] * math.cos(curve1Angle[i] + (currentAngle))
                involutePoints[i].y = curve1Dist[i] * math.sin(curve1Angle[i] + (currentAngle))

                involute2Points[i].x = curve2Dist[i] * math.cos(curve2Angle[i] + (currentAngle))
                involute2Points[i].y = curve2Dist[i] * math.sin(curve2Angle[i] + (currentAngle))

            sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), rootDiameter/2)

            sketch.isComputeDeferred = False
            # Create the extrusion.
            profOne = sketch.profiles[0]
            extOne = createExtrude(profOne, thickness)
            profTwo = sketch.profiles[1]
            extTwo = createExtrude(profTwo, thickness)

            circularPatterns = newComp.features.circularPatternFeatures
            entities = adsk.core.ObjectCollection.create()
            entities.add(extTwo)
            circularPatternInput = circularPatterns.createInput(entities, getCylinderFace(extOne))
            circularPatternInput.quantity = adsk.core.ValueInput.createByString(str(numTeeth))
            circularPatterns.add(circularPatternInput)

            fc = extOne.faces[0]
            bd = fc.body

            bd.name = 'Gear (' + str(round(pitchDia, 2)) + ' pitch dia.)'

        # add a command on create panel in modeling workspace
        commandName = 'Create Spur Gear'
        commandDescription = 'Create a spur gear.'
        workspaces_ = ui.workspaces
        modelingWorkspace_ = workspaces_.itemById('FusionSolidEnvironment')
        toolbarPanels_ = modelingWorkspace_.toolbarPanels
        toolbarPanel_ = toolbarPanels_.item(0) # add the new command under the first panel
        toolbarControls_ = toolbarPanel_.controls
        toolbarControl_ = toolbarControls_.itemById(commandId)
        if toolbarControl_:
            ui.messageBox('SpurGear command is already loaded.')
            adsk.terminate()
            return
        else:
            commandDefinition_ = ui.commandDefinitions.itemById(commandId)
            if not commandDefinition_:
                resourceDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
                commandDefinition_ = ui.commandDefinitions.addButtonDefinition(commandId, commandName, commandDescription, resourceDir)
            onCommandCreated = SpurGearCommandCreatedHandler()
            commandDefinition_.commandCreated.add(onCommandCreated)
            # keep the handler referenced beyond this function
            handlers.append(onCommandCreated)
            toolbarControl_ = toolbarControls_.addCommand(commandDefinition_, commandId)
            toolbarControl_.isVisible = True

            if context['IsApplicationStartup'] == False:
                ui.messageBox('SpurGear is loaded successfully.\r\n\r\nA command is added to the create panel in modeling workspace.')

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()

def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        objArray = []

        commandControl_ = commandControlById(commandId)
        if commandControl_:
            objArray.append(commandControl_)

        commandDefinition_ = commandDefinitionById(commandId)
        if commandDefinition_:
            objArray.append(commandDefinition_)

        for obj in objArray:
            destroyObject(ui, obj)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
