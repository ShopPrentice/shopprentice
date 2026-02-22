#Author-Autodesk Inc
#Description-Create bolt

import adsk.core, adsk.fusion, traceback
import math

defaultBoltName = 'Bolt'
defaultHeadDiameter = 0.75
defaultBodyDiameter = 0.5
defaultHeadHeight = 0.3125
defaultBodyLength = 2.0
defaultCutAngle = 30.0 * (math.pi / 180)
defaultChamferDistance = 0.03845
defaultFilletRadius = 0.02994

# global set of event handlers to keep them referenced for the duration of the command
handlers = []
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

class BoltCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            unitsMgr = app.activeProduct.unitsManager
            command = args.firingEvent.sender
            inputs = command.commandInputs

            bolt = Bolt()
            for input in inputs:
                if input.id == 'boltName':
                    bolt.boltName = input.value
                elif input.id == 'headDiameter':
                    bolt.headDiameter = unitsMgr.evaluateExpression(input.expression, "cm")
                elif input.id == 'bodyDiameter':
                    bolt.bodyDiameter = unitsMgr.evaluateExpression(input.expression, "cm")
                elif input.id == 'headHeight':
                    bolt.headHeight = unitsMgr.evaluateExpression(input.expression, "cm")
                elif input.id == 'bodyLength':
                    bolt.bodyLength = adsk.core.ValueInput.createByString(input.expression)
                elif input.id == 'cutAngle':
                    bolt.cutAngle = unitsMgr.evaluateExpression(input.expression, "deg")
                elif input.id == 'chamferDistance':
                    bolt.chamferDistance = adsk.core.ValueInput.createByString(input.expression)
                elif input.id == 'filletRadius':
                    bolt.filletRadius = adsk.core.ValueInput.createByString(input.expression)

            bolt.buildBolt();
            args.isValidResult = True

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class BoltCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class BoltCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = BoltCommandExecuteHandler()
            cmd.execute.add(onExecute)
            onExecutePreview = BoltCommandExecuteHandler()
            cmd.executePreview.add(onExecutePreview)
            onDestroy = BoltCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            # keep the handler referenced beyond this function
            handlers.append(onExecute)
            handlers.append(onExecutePreview)
            handlers.append(onDestroy)

            #define the inputs
            inputs = cmd.commandInputs
            inputs.addStringValueInput('boltName', 'Blot Name', defaultBoltName)

            initHeadDiameter = adsk.core.ValueInput.createByReal(defaultHeadDiameter)
            inputs.addValueInput('headDiameter', 'Head Diameter','cm',initHeadDiameter)

            initBodyDiameter = adsk.core.ValueInput.createByReal(defaultBodyDiameter)
            inputs.addValueInput('bodyDiameter', 'Body Diameter', 'cm', initBodyDiameter)

            initHeadHeight = adsk.core.ValueInput.createByReal(defaultHeadHeight)
            inputs.addValueInput('headHeight', 'Head Height', 'cm', initHeadHeight)

            initBodyLength = adsk.core.ValueInput.createByReal(defaultBodyLength)
            inputs.addValueInput('bodyLength', 'Body Length', 'cm', initBodyLength)

            #to do the thread length

            initCutAngle = adsk.core.ValueInput.createByReal(defaultCutAngle)
            inputs.addValueInput('cutAngle', 'Cut Angle', 'deg', initCutAngle)

            initChamferDistance = adsk.core.ValueInput.createByReal(defaultChamferDistance)
            inputs.addValueInput('chamferDistance', 'Chamfer Distance', 'cm', initChamferDistance)

            initFilletRadius = adsk.core.ValueInput.createByReal(defaultFilletRadius)
            inputs.addValueInput('filletRadius', 'Fillet Radius', 'cm', initFilletRadius)
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class Bolt:
    def __init__(self):
        self._boltName = defaultBoltName
        self._headDiameter = defaultHeadDiameter
        self._bodyDiameter = defaultBodyDiameter
        self._headHeight = defaultHeadHeight
        self._bodyLength = adsk.core.ValueInput.createByReal(defaultBodyLength)
        self._cutAngle = defaultCutAngle
        self._chamferDistance = adsk.core.ValueInput.createByReal(defaultChamferDistance)
        self._filletRadius = adsk.core.ValueInput.createByReal(defaultFilletRadius)

    #properties
    @property
    def boltName(self):
        return self._boltName
    @boltName.setter
    def boltName(self, value):
        self._boltName = value

    @property
    def headDiameter(self):
        return self._headDiameter
    @headDiameter.setter
    def headDiameter(self, value):
        self._headDiameter = value

    @property
    def bodyDiameter(self):
        return self._bodyDiameter
    @bodyDiameter.setter
    def bodyDiameter(self, value):
        self._bodyDiameter = value

    @property
    def headHeight(self):
        return self._headHeight
    @headHeight.setter
    def headHeight(self, value):
        self._headHeight = value

    @property
    def bodyLength(self):
        return self._bodyLength
    @bodyLength.setter
    def bodyLength(self, value):
        self._bodyLength = value

    @property
    def cutAngle(self):
        return self._cutAngle
    @cutAngle.setter
    def cutAngle(self, value):
        self._cutAngle = value

    @property
    def chamferDistance(self):
        return self._chamferDistance
    @chamferDistance.setter
    def chamferDistance(self, value):
        self._chamferDistance = value

    @property
    def filletRadius(self):
        return self._filletRadius
    @filletRadius.setter
    def filletRadius(self, value):
        self._filletRadius = value

    def buildBolt(self):
        global newComp
        newComp = createNewComponent()
        if newComp is None:
            ui.messageBox('New component failed to create', 'New Component Failed')
            return

        # Create a new sketch.
        sketches = newComp.sketches
        xyPlane = newComp.xYConstructionPlane
        xzPlane = newComp.xZConstructionPlane
        sketch = sketches.add(xyPlane)
        center = adsk.core.Point3D.create(0, 0, 0)
        vertices = []
        for i in range(0, 6):
            vertex = adsk.core.Point3D.create(center.x + (self.headDiameter/2) * math.cos(math.pi * i / 3), center.y + (self.headDiameter/2) * math.sin(math.pi * i / 3),0)
            vertices.append(vertex)

        for i in range(0, 6):
            sketch.sketchCurves.sketchLines.addByTwoPoints(vertices[(i+1) %6], vertices[i])

        extrudes = newComp.features.extrudeFeatures
        prof = sketch.profiles[0]
        extInput = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

        distance = adsk.core.ValueInput.createByReal(self.headHeight)
        extInput.setDistanceExtent(False, distance)
        headExt = extrudes.add(extInput)

        fc = headExt.faces[0]
        bd = fc.body
        bd.name = self.boltName

        #create the body
        bodySketch = sketches.add(xyPlane)
        bodySketch.sketchCurves.sketchCircles.addByCenterRadius(center, self.bodyDiameter/2)

        bodyProf = bodySketch.profiles[0]
        bodyExtInput = extrudes.createInput(bodyProf, adsk.fusion.FeatureOperations.JoinFeatureOperation)

        bodyExtInput.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
        bodyExtInput.setDistanceExtent(False, self.bodyLength)
        bodyExt = extrudes.add(bodyExtInput)

        # create chamfer
        edgeCol = adsk.core.ObjectCollection.create()
        edges = bodyExt.endFaces[0].edges
        for edgeI  in edges:
            edgeCol.add(edgeI)

        chamferFeats = newComp.features.chamferFeatures
        chamferInput = chamferFeats.createInput(edgeCol, True)
        chamferInput.setToEqualDistance(self.chamferDistance)
        chamferFeats.add(chamferInput)

        # create fillet
        edgeCol.clear()
        loops = headExt.endFaces[0].loops
        edgeLoop = None
        for edgeLoop in loops:
            #since there two edgeloops in the start face of head, one consists of one circle edge while the other six edges
            if(len(edgeLoop.edges) == 1):
                break

        edgeCol.add(edgeLoop.edges[0])
        filletFeats = newComp.features.filletFeatures
        filletInput = filletFeats.createInput()
        filletInput.addConstantRadiusEdgeSet(edgeCol, self.filletRadius, True)
        filletFeats.add(filletInput)

        #create revolve feature 1
        revolveSketchOne = sketches.add(xzPlane)
        radius = self.headDiameter/2
        point1 = revolveSketchOne.modelToSketchSpace(adsk.core.Point3D.create(center.x + radius*math.cos(math.pi/6), 0, center.y))
        point2 = revolveSketchOne.modelToSketchSpace(adsk.core.Point3D.create(center.x + radius, 0, center.y))

        point3 = revolveSketchOne.modelToSketchSpace(adsk.core.Point3D.create(point2.x, 0, (point2.x - point1.x) * math.tan(self.cutAngle)))
        revolveSketchOne.sketchCurves.sketchLines.addByTwoPoints(point1, point2)
        revolveSketchOne.sketchCurves.sketchLines.addByTwoPoints(point2, point3)
        revolveSketchOne.sketchCurves.sketchLines.addByTwoPoints(point3, point1)

        #revolve feature 2
        point4 = revolveSketchOne.modelToSketchSpace(adsk.core.Point3D.create(center.x + radius*math.cos(math.pi/6), 0, self.headHeight - center.y))
        point5 = revolveSketchOne.modelToSketchSpace(adsk.core.Point3D.create(center.x + radius, 0, self.headHeight - center.y))
        point6 = revolveSketchOne.modelToSketchSpace(adsk.core.Point3D.create(center.x + point2.x, 0, self.headHeight - center.y - (point5.x - point4.x) * math.tan(self.cutAngle)))
        revolveSketchOne.sketchCurves.sketchLines.addByTwoPoints(point4, point5)
        revolveSketchOne.sketchCurves.sketchLines.addByTwoPoints(point5, point6)
        revolveSketchOne.sketchCurves.sketchLines.addByTwoPoints(point6, point4)

        zaxis = newComp.zConstructionAxis
        revolves = newComp.features.revolveFeatures
        revProf1 = revolveSketchOne.profiles[0]
        revInput1 = revolves.createInput(revProf1, zaxis, adsk.fusion.FeatureOperations.CutFeatureOperation)

        revAngle = adsk.core.ValueInput.createByReal(math.pi*2)
        revInput1.setAngleExtent(False,revAngle)
        revolves.add(revInput1)

        revProf2 = revolveSketchOne.profiles[1]
        revInput2 = revolves.createInput(revProf2, zaxis, adsk.fusion.FeatureOperations.CutFeatureOperation)

        revInput2.setAngleExtent(False,revAngle)
        revolves.add(revInput2)

        sideFace = bodyExt.sideFaces[0]
        threads = newComp.features.threadFeatures
        threadDataQuery = threads.threadDataQuery
        defaultThreadType = threadDataQuery.defaultMetricThreadType
        recommendData = threadDataQuery.recommendThreadData(self.bodyDiameter, False, defaultThreadType)
        if recommendData[0] :
            threadInfo = threads.createThreadInfo(False, defaultThreadType, recommendData[1], recommendData[2])
            threadInput = threads.createInput(sideFace, threadInfo)
            threads.add(threadInput)
def main():
    try:
        commandDefinitions = ui.commandDefinitions
        #check the command exists or not
        cmdDef = commandDefinitions.itemById('Bolt')
        if not cmdDef:
            cmdDef = commandDefinitions.addButtonDefinition('Bolt',
                    'Create Bolt',
                    'Create a bolt.',
                    './resources') # relative resource file path is specified

        onCommandCreated = BoltCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        # keep the handler referenced beyond this function
        handlers.append(onCommandCreated)
        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event handlers to fire
        adsk.autoTerminate(False)
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
main()
