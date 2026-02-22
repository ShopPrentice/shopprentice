#Author-Autodesk Inc.
#Description-Select a path to create a pipe.

import adsk.core, adsk.fusion, traceback

pipeRadius = 2.5
pipeThickness = '5mm'
    
def main():
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        
        sel = ui.selectEntity('Select a path to create a pipe', 'Edges,SketchCurves')
        selObj = sel.entity
        
        comp = app.activeProduct.rootComponent
        
        # create path
        feats = comp.features
        path = feats.createPath(selObj)
        
        # create profile
        planes = comp.constructionPlanes
        planeInput = planes.createInput()
        planeInput.setByDistanceOnPath(selObj, adsk.core.ValueInput.createByReal(0))
        plane = planes.add(planeInput)
        
        sketches = comp.sketches
        sketch = sketches.add(plane)
        
        center = plane.geometry.origin
        center = sketch.modelToSketchSpace(center)
        sketch.sketchCurves.sketchCircles.addByCenterRadius(center, pipeRadius)
        profile = sketch.profiles[0]
        
        # create sweep
        sweepFeats = feats.sweepFeatures
        sweepInput = sweepFeats.createInput(profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        sweepInput.orientation = adsk.fusion.SweepOrientationTypes.ParallelOrientationType
        sweepFeat = sweepFeats.add(sweepInput)
        
        # create shell
        startFaces = sweepFeat.startFaces
        endFaces = sweepFeat.endFaces
        
        objCol = adsk.core.ObjectCollection.create()
        for startFace in startFaces:
            objCol.add(startFace)
        for endFace in endFaces:
            objCol.add(endFace)
        
        shellFeats = feats.shellFeatures
        shellInput = shellFeats.createInput(objCol, False)
        shellInput.insideThickness = adsk.core.ValueInput.createByString(pipeThickness)
        shellFeats.add(shellInput)
        
        app.activeViewport.refresh()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

main()
