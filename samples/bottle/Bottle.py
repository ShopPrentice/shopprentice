#Author-Autodesk Inc.
#Description-Create a bottle.

import adsk.core, adsk.fusion, traceback, math

# scale of the bottle size
scale = 2.0

# unit - cm
height = 21
topWidth = 2.8
topHight = 1.9
bodyTopWidth = 0.4
bottomWidth = 3.2
upperArcCenterToTop = 4.5
upperArcRadius = 16
lowerArcRadius = 15
filletRadius = 0.5
thickness = 0.3
threadPitch = 0.4

# used for direct modeling
upperArcMidPtXOffset = -0.18
upperArcMidPtYOffset = -4.1
upperArcEndPtXOffset = 0.46
upperArcEndPtYOffset = -7.2
lowerArcMidPtXOffsetFromOriginPt = 4.66
lowerArcMidPtYOffsetFromOriginPt = 5.9

bottomCenter = adsk.core.Point3D.create(0, 0, 0)
bottleMaterial = 'PrismMaterial-006'
bottleAppearance = 'Prism-154'
materialLibId = 'C1EEA57C-3F56-45FC-B8CB-A9EC46A9994C'
appearanceLibId = 'BA5EE55E-9982-449B-9D66-9F036540E140'

nearZero = 0.000001

app = adsk.core.Application.get()
ui  = app.userInterface

newComp = None

def createNewComponent():
    # Get the active design.
    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    rootComp = design.rootComponent
    allOccs = rootComp.occurrences
    newOcc = allOccs.addNewComponent(adsk.core.Matrix3D.create())
    return newOcc.component

def createBottle():
    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    currentDesignType = design.designType

    global newComp
    newComp = createNewComponent()
    if newComp is None:
        ui.messageBox('New component failed to create', 'New Component Failed')
        return

    # add sketch
    sketches = newComp.sketches
    sketch = sketches.add(newComp.xYConstructionPlane)

    # add sketch curves
    sketchlines = sketch.sketchCurves.sketchLines

    endPt = bottomCenter.copy() #start from bottomCenter
    endPt.y = bottomCenter.y + height
    heightLine = sketchlines.addByTwoPoints(bottomCenter, endPt)

    endPt.x = endPt.x + topWidth
    topLine = sketchlines.addByTwoPoints(heightLine.endSketchPoint, endPt)

    endPt.y = endPt.y - topHight
    topHightLine = sketchlines.addByTwoPoints(topLine.endSketchPoint, endPt)

    endPt.x = endPt.x + bodyTopWidth
    topBodyLine = sketchlines.addByTwoPoints(topHightLine.endSketchPoint, endPt)

    sketchArcs = sketch.sketchCurves.sketchArcs

    if currentDesignType == adsk.fusion.DesignTypes.DirectDesignType:
        endPt.x = topBodyLine.endSketchPoint.geometry.x + upperArcEndPtXOffset
        endPt.y = topBodyLine.endSketchPoint.geometry.y + upperArcEndPtYOffset
        ptOnArc = adsk.core.Point3D.create(topBodyLine.endSketchPoint.geometry.x + upperArcMidPtXOffset, topBodyLine.endSketchPoint.geometry.y + upperArcMidPtYOffset)
        upperArc = sketchArcs.addByThreePoints(topBodyLine.endSketchPoint, ptOnArc, endPt)

        endPt = bottomCenter.copy()
        endPt.x = bottomWidth
        ptOnArc = adsk.core.Point3D.create(lowerArcMidPtXOffsetFromOriginPt, lowerArcMidPtYOffsetFromOriginPt)
    else:
        deltPos = 0.1
        endPt.x = topWidth + bodyTopWidth + bodyTopWidth
        endPt.y = height / 2
        ptOnArc = adsk.core.Point3D.create(endPt.x - deltPos, endPt.y + deltPos)
        upperArc = sketchArcs.addByThreePoints(topBodyLine.endSketchPoint, ptOnArc, endPt)

        endPt = bottomCenter.copy()
        endPt.x = bottomWidth
        ptOnArc = adsk.core.Point3D.create(endPt.x + deltPos, endPt.y + deltPos)

    lowerArc = sketchArcs.addByThreePoints(upperArc.endSketchPoint, ptOnArc, endPt)
    buttomLine = sketchlines.addByTwoPoints(lowerArc.startSketchPoint, heightLine.startSketchPoint)

    # add constraints
    heightLine.startSketchPoint.isFixed = True
    sketchConstraints = sketch.geometricConstraints
    sketchConstraints.addHorizontal(buttomLine)
    sketchConstraints.addPerpendicular(buttomLine, heightLine)
    sketchConstraints.addPerpendicular(heightLine, topLine)
    sketchConstraints.addPerpendicular(topLine, topHightLine)
    sketchConstraints.addPerpendicular(topHightLine, topBodyLine)

    # add dimensions
    sketchDims = sketch.sketchDimensions

    startPt = heightLine.startSketchPoint.geometry
    endPt = heightLine.endSketchPoint.geometry
    textPos = adsk.core.Point3D.create((startPt.x + endPt.x) / 2, (startPt.y + endPt.y) / 2, 0)
    textPos.x = textPos.x - 1
    sketchDims.addDistanceDimension(heightLine.startSketchPoint, heightLine.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPos)

    startPt = topLine.startSketchPoint.geometry
    endPt = topLine.endSketchPoint.geometry
    textPos = adsk.core.Point3D.create((startPt.x + endPt.x) / 2, (startPt.y + endPt.y) / 2, 0)
    textPos.y = textPos.y + 1
    sketchDims.addDistanceDimension(topLine.startSketchPoint, topLine.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPos)

    startPt = topHightLine.startSketchPoint.geometry
    endPt = topHightLine.endSketchPoint.geometry
    textPos = adsk.core.Point3D.create((startPt.x + endPt.x) / 2, (startPt.y + endPt.y) / 2, 0)
    textPos.x = textPos.x + 1
    sketchDims.addDistanceDimension(topHightLine.startSketchPoint, topHightLine.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPos)

    startPt = topBodyLine.startSketchPoint.geometry
    endPt = topBodyLine.endSketchPoint.geometry
    textPos = adsk.core.Point3D.create((startPt.x + endPt.x) / 2, (startPt.y + endPt.y) / 2, 0)
    textPos.y = textPos.y + 1
    sketchDims.addDistanceDimension(topBodyLine.startSketchPoint, topBodyLine.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPos)

    startPt = buttomLine.startSketchPoint.geometry
    endPt = buttomLine.endSketchPoint.geometry
    textPos = adsk.core.Point3D.create((startPt.x + endPt.x) / 2, (startPt.y + endPt.y) / 2, 0)
    textPos.y = textPos.y - 1
    sketchDims.addDistanceDimension(buttomLine.startSketchPoint, buttomLine.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation, textPos)

    startPt = topLine.endSketchPoint.geometry
    endPt = upperArc.centerSketchPoint.geometry
    textPos = adsk.core.Point3D.create((startPt.x + endPt.x) / 2, (startPt.y + endPt.y) / 2, 0)
    if currentDesignType == adsk.fusion.DesignTypes.DirectDesignType:
        sketchDims.addDistanceDimension(topLine.endSketchPoint, upperArc.centerSketchPoint, adsk.fusion.DimensionOrientations.VerticalDimensionOrientation, textPos)
    else:
        distDim = sketchDims.addDistanceDimension(topLine.endSketchPoint, upperArc.centerSketchPoint, adsk.fusion.DimensionOrientations.VerticalDimensionOrientation, textPos)
        distDim.parameter.value = upperArcCenterToTop

        startPt = upperArc.centerSketchPoint.geometry
        textPos = adsk.core.Point3D.create(startPt.x + deltPos, startPt.y, 0)
        radialArc = sketchDims.addRadialDimension(upperArc, textPos)
        radialArc.parameter.value = upperArcRadius

        startPt = lowerArc.centerSketchPoint.geometry
        textPos = adsk.core.Point3D.create(startPt.x + deltPos, startPt.y, 0)
        radialArc = sketchDims.addRadialDimension(lowerArc, textPos)
        radialArc.parameter.value = lowerArcRadius

    # create revolve
    revolveFeats = newComp.features.revolveFeatures

    revolveInput = revolveFeats.createInput(sketch.profiles[0], heightLine, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    revolveInput.setAngleExtent(True, adsk.core.ValueInput.createByReal(2 * math.pi))
    revolveFeat = revolveFeats.add(revolveInput)

    # create fillets
    filletFeats = newComp.features.filletFeatures

    # select the edges to do fillets
    faces = revolveFeat.faces
    body = faces[0].body
    edgeCol = adsk.core.ObjectCollection.create()
    for edge in body.edges:
        circle = edge.geometry
        if math.fabs(circle.radius - bottomWidth) < nearZero or math.fabs(circle.radius - topWidth - bodyTopWidth) < nearZero:
            edgeCol.add(edge)

    filletInput = filletFeats.createInput()
    filletInput.addConstantRadiusEdgeSet(edgeCol, adsk.core.ValueInput.createByReal(filletRadius), True)
    filletFeats.add(filletInput)

    # create shell
    shellFeats = newComp.features.shellFeatures

    # select the faces to remove
    faceCol = adsk.core.ObjectCollection.create()
    for face in faces:
        # find the top face
        if face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
            edge0 = face.edges[0]
            if edge0.geometry.center.isEqualTo(heightLine.endSketchPoint.worldGeometry):
                faceCol.add(face)
                break

    shellInput = shellFeats.createInput(faceCol)
    shellInput.insideThickness = adsk.core.ValueInput.createByReal(thickness)
    shellFeats.add(shellInput)

    # create thread
    threadFeats = newComp.features.threadFeatures

    # select the face to do thread
    threadFace = None
    for faceTemp in faces:
        surf = faceTemp.geometry
        if surf.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType and math.fabs(surf.radius - topWidth) < nearZero:
            threadFace = faceTemp
            break

    threadQuery = threadFeats.threadDataQuery
    threadType = threadQuery.defaultMetricThreadType
    designation = ''
    threadClass = ''
    results = threadQuery.recommendThreadData(topWidth * 2, False, threadType)
    if results[0]:
        designation = results[1]
        threadClass = results[2]

    # find closest thread pitch
    threadInfo = threadFeats.createThreadInfo(False, threadType, designation, threadClass)
    designations = threadQuery.allDesignations(threadType, threadInfo.threadSize)
    minGap = math.fabs(threadInfo.threadPitch - threadPitch)
    for des in designations :
        tempThreadInfo = threadFeats.createThreadInfo(False, threadType, des, threadClass)
        tempGap = math.fabs(tempThreadInfo.threadPitch - threadPitch)
        if tempGap < minGap :
            threadInfo = tempThreadInfo
            minGap = tempGap

    threadInput = threadFeats.createInput(threadFace, threadInfo)
    threadInput.isModeled = True
    threadFeats.add(threadInput)

    # create scale
    scaleFeats = newComp.features.scaleFeatures

    objCol = adsk.core.ObjectCollection.create()
    objCol.add(body)

    scaleInput = scaleFeats.createInput(objCol, newComp.originConstructionPoint, adsk.core.ValueInput.createByReal(scale))
    scaleFeats.add(scaleInput)

    # set material
    materialLibs = app.materialLibraries
    materials = materialLibs.itemById(materialLibId).materials
    appearances = materialLibs.itemById(appearanceLibId).appearances

    body.material = materials.itemById(bottleMaterial)
    body.appearance = appearances.itemById(bottleAppearance)

    app.activeViewport.refresh()

def main():
    try:
        createBottle()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

main()
