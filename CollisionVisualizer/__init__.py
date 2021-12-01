import math
from Mods import ModMenu
from unrealsdk import FindAll, FStruct, GetEngine, Log, RemoveHook, RunHook, UFunction, UObject

class CollisionVisualizer(ModMenu.SDKMod):
    Name = "Collision Visualizer"
    Version = "0.1.0"
    Author = "None"
    Description = "Visualizes invisible blocking/killing collision volumes and allows hiding meshes with no collision."
    SupportedGames = ModMenu.Game.BL2 | ModMenu.Game.TPS | ModMenu.Game.AoDK
    Types = ModMenu.ModTypes.Utility

    Keybinds = [
        ModMenu.Keybind("Toggle Kill Volumes", "F2"),
        ModMenu.Keybind("Toggle Collision Volumes", "F3"),
        ModMenu.Keybind("Toggle Fake Meshes", "F5"),
    ]

    def showMessage(self, message, title = "Collision Visualizer"):
        pc = GetEngine().GamePlayers[0].Actor
        movie = pc.myHUD.HUDMovie
        try:
            if pc is None or movie is None:
                return True
            movie.AddTrainingText(message, title, 3, (), "", False, 0, pc.PlayerReplicationInfo, True, 0, 0)
        except:
            return True
        return True

    def log(self, message):
        Log(message)

    killData = {}
    collisionData = {}
    nextColors = [0, 0]
    colorSlot = 0

    colors = [
        (255, 0, 0),   # red
        (0, 255, 0),   # green
        (0, 0, 255),   # blue
        (0, 255, 255), # cyan
        (255, 0, 255), # magenta
        (255, 255, 0)  # yellow
    ]

    def startDrawingVolumes(self, classNames, names, master):
        if not isinstance(classNames, list):
            classNames = [classNames]
        if not isinstance(names, list):
            names = [names]
        msg = ""
        pc = GetEngine().GamePlayers[0].Actor
        if pc is None:
            self.showMessage("No player")
            return
        for className, name in zip(classNames, names):
            if className in master:
                collection = master[className]
                count = 0
                for key in collection:
                    count += 1
                    info = collection[key]
                    verts = info["verts"]
                    tris = info["tris"]
                    color = info["color"]
                    i = 0
                    while i < len(tris):
                        pc.DrawDebugLine(verts[tris[i + 0]], verts[tris[i + 1]], color[0], color[1], color[2], True, 86400)
                        pc.DrawDebugLine(verts[tris[i + 1]], verts[tris[i + 2]], color[0], color[1], color[2], True, 86400)
                        pc.DrawDebugLine(verts[tris[i + 2]], verts[tris[i + 0]], color[0], color[1], color[2], True, 86400)
                        i += 3
                if msg != "":
                    msg += "\n"
                msg += f"{name}: {count}"
        if msg != "":
            self.showMessage(msg)

    def resetAll(self):
        self.showKill = False
        self.showCollision = False
        self.clearAllVolumes()
        self.nextColors = [0, 0]

    def clearAllVolumes(self):
        self.killData = {}
        self.collisionData = {}
        pc = GetEngine().GamePlayers[0].Actor
        if pc is not None:
            pc.FlushPersistentDebugLines()
        self.hideFake = False
        self.hiddenComponents = []

    def stopDrawingVolumes(self):
        pc = GetEngine().GamePlayers[0].Actor
        if pc is not None:
            pc.FlushPersistentDebugLines()
        self.showMessage("Stopped drawing")

    def updateVolumes(self, classNames, master):
        if not isinstance(classNames, list):
            classNames = [classNames]
        for className in classNames:
            if className in master:
                collection = master[className]
            else:
                collection = {}
                master[className] = collection
            allVolumes = FindAll(className)
            allVolumes = [v for v in allVolumes if "PersistentLevel" in v.GetFullName()]
            #allVolumes = [v for v in allVolumes if "Loader.TheWorld" not in v.GetFullName()]
            for volume in allVolumes:
                if className in ["BlockingMeshCollectionActor", "SeqEvent_Touch"] or not volume in collection:
                    if className == "BlockingMeshActor":
                        result = self.addBlockingMeshComponent(volume.CollisionComponent, collection, volume)
                    elif className == "BlockingMeshCollectionActor":
                        result = self.addBlockingMeshCollection(volume, collection)
                    elif className == "WillowBoundaryTurret":
                        result = self.addBoundaryTurret(volume, collection)
                    elif className == "SeqEvent_Touch":
                        result = self.addTouchVolume(volume, collection)
                    elif className == "BehaviorVolume":
                        result = self.addBehaviorVolume(volume, collection)
                    else:
                        result = self.addNewVolume(volume, collection)
                    if result:
                        self.log(f"added: {volume}")

    def addBehaviorVolume(self, volume, collection):
        if volume.Definition is not None and "BehaviorVolume_KillPawn" in volume.Definition.GetFullName():
            return self.addNewVolume(volume, collection)
        return False

    def addTouchVolume(self, seqEvent, collection):
        volume = seqEvent.Originator
        if volume is not None and "TriggerVolume" in volume.GetFullName() and not volume in collection:
            for output in seqEvent.OutputLinks:
                for link in output.Links:
                    if "SeqAct_CausePlayerDeath" in link.LinkedOp.GetFullName():
                        return self.addNewVolume(volume, collection)
        return False

    def addBoundaryTurret(self, turret, collection):
        height = 10000
        v0 = self.rotatePoint((turret.KillDistance, -turret.ViewWidth, -height), 0, turret.Rotation.Yaw, 0)
        v1 = self.rotatePoint((turret.KillDistance, -turret.ViewWidth, height), 0, turret.Rotation.Yaw, 0)
        v2 = self.rotatePoint((turret.KillDistance, turret.ViewWidth, height), 0, turret.Rotation.Yaw, 0)
        v3 = self.rotatePoint((turret.KillDistance, turret.ViewWidth, -height), 0, turret.Rotation.Yaw, 0)
        v0 = (v0[0] + turret.Location.X, v0[1] + turret.Location.Y, v0[2] + turret.Location.Z)
        v1 = (v1[0] + turret.Location.X, v1[1] + turret.Location.Y, v1[2] + turret.Location.Z)
        v2 = (v2[0] + turret.Location.X, v2[1] + turret.Location.Y, v2[2] + turret.Location.Z)
        v3 = (v3[0] + turret.Location.X, v3[1] + turret.Location.Y, v3[2] + turret.Location.Z)
        vertices = [v0, v1, v2, v3]
        tris = [0, 1, 2, 2, 3, 0]
        self.addEntity(turret, vertices, tris, collection, 3)

    def addNewVolume(self, volume, collection):
        self.warnIfComplicated(volume)
        for elem in volume.CollisionComponent.BrushAggGeom.ConvexElems:
            vertices = []
            tris = []
            for item in elem.VertexData:
                vertices.append((item.X + volume.Location.X, item.Y + volume.Location.Y, item.Z + volume.Location.Z))
            for item in elem.FaceTriData:
                tris.append(item)
            self.addEntity(volume, vertices, tris, collection)
            break
        return True

    def addEntity(self, volume, vertices, tris, collection, subdivisions = 2):
        vertMap = {}
        for _ in range(subdivisions):
            i = 0
            length = len(tris)
            while i < length:
                v1 = tris[i]
                v2 = tris[i + 1]
                v3 = tris[i + 2]
                area = self.triArea(vertices[v1], vertices[v2], vertices[v3])
                if area >= 1000:
                    newTris = self.subdivide(v1, v2, v3, vertices, vertMap)
                    tris = tris[0:i] + newTris + tris[i + 3:]
                    length += len(newTris) - 3
                    i += len(newTris)
                else:
                    i += 3
        colorIndex = self.nextColors[self.colorSlot]
        color = self.colors[colorIndex]
        collection[volume] = { "verts": vertices, "tris": tris, "color": color }
        colorIndex += 1
        if colorIndex >= len(self.colors):
            colorIndex = 0
        self.nextColors[self.colorSlot] = colorIndex

    def addBlockingMeshCollection(self, volume, collection):
        addedAny = False
        for component in volume.Components:
            if not component in collection:
                if self.addBlockingMeshComponent(component, collection, component):
                    addedAny = True
        return addedAny

    def doesBlockerBlock(self, component):
        return component.bBlockPlayers and component.CollideActors and component.BlockActors and component.BlockNonZeroExtent

    def addBlockingMeshComponent(self, component, collection, key):
        if component is None or not self.doesBlockerBlock(component):
            return False
        if component.bIsDisabled:
            self.log("note: found bIsDisabled BlockingMeshComponent")
        mesh = component.StaticMesh
        geom = mesh.BodySetup.AggGeom
        meshName = mesh.GetFullName()
        vertices = []
        tris = []
        if self.iterLen(geom.SphereElems) > 0:
            self.log(f"Could not add BlockingMeshActor with SphereElems")
            return False
        if self.iterLen(geom.SphylElems) > 0:
            self.log(f"Could not add BlockingMeshActor with SphylElems")
            return False
        if self.iterLen(geom.BoxElems) + self.iterLen(geom.ConvexElems) > 1:
            self.log(f"Could not add BlockingMeshActor with multiple BoxElems/ConvexElems")
            return False
        if self.iterLen(geom.ConvexElems) == 1:
            if not "Common_Meshes.Blocking.Blocking_Cylinder" in meshName:
                self.log(f'note: non-Cylinder BlockingMeshActor w/ ConvexElem: "{meshName}"')
            for vertex in geom.ConvexElems[0].VertexData:
                vertices.append(self.transformPoint((vertex.X, vertex.Y, vertex.Z), component._LocalToWorld))
            for tri in geom.ConvexElems[0].FaceTriData:
                tris.append(tri)
        elif self.iterLen(geom.BoxElems) == 1:
            if not "Common_Meshes.Blocking.Blocking_Cube" in meshName:
                self.log(f'non-Cube BlockingMeshActor w/ BoxElem: "{meshName}"')
                return False
            size = 256
            vertices.append(self.transformPoint((0, 0, 0), component._LocalToWorld))
            vertices.append(self.transformPoint((0, 0, size), component._LocalToWorld))
            vertices.append(self.transformPoint((0, size, size), component._LocalToWorld))
            vertices.append(self.transformPoint((0, size, 0), component._LocalToWorld))
            vertices.append(self.transformPoint((size, 0, 0), component._LocalToWorld))
            vertices.append(self.transformPoint((size, 0, size), component._LocalToWorld))
            vertices.append(self.transformPoint((size, size, size), component._LocalToWorld))
            vertices.append(self.transformPoint((size, size, 0), component._LocalToWorld))
            tris = [
                0, 1, 2, 2, 3, 0,
                4, 5, 1, 1, 0, 4,
                7, 6, 5, 5, 4, 7,
                3, 2, 6, 6, 7, 3,
                1, 5, 6, 6, 2, 1,
                4, 0, 3, 3, 7, 4
            ]
        else:
            # strictly speaking, this is a box with an X extent of 1.0 units, but we're just drawing a plane
            if not "Common_Meshes.Blocking.Blocking_Plane" in meshName:
                self.log(f'non-Plane BlockingMeshActor w/ no AggGeom: "{meshName}"')
                return False
            size = 256
            vertices.append(self.transformPoint((0, 0, 0), component._LocalToWorld))
            vertices.append(self.transformPoint((0, 0, size), component._LocalToWorld))
            vertices.append(self.transformPoint((0, size, size), component._LocalToWorld))
            vertices.append(self.transformPoint((0, size, 0), component._LocalToWorld))
            tris = [0, 1, 2, 2, 3, 0]
        self.addEntity(key, vertices, tris, collection)
        return True

    def subdivide(self, i1, i2, i3, verts, vertMap):
        e1 = vertMap.get((i1, i2), None)
        if e1 is None:
            v1 = verts[i1]
            v2 = verts[i2]
            verts.append(((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2, (v1[2] + v2[2]) / 2))
            e1 = len(verts) - 1
            vertMap[(i1, i2)] = e1
        e2 = vertMap.get((i2, i3), None)
        if e2 is None:
            v1 = verts[i2]
            v2 = verts[i3]
            verts.append(((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2, (v1[2] + v2[2]) / 2))
            e2 = len(verts) - 1
            vertMap[(i2, i3)] = e2
        e3 = vertMap.get((i1, i3), None)
        if e3 is None:
            v1 = verts[i1]
            v2 = verts[i3]
            verts.append(((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2, (v1[2] + v2[2]) / 2))
            e3 = len(verts) - 1
            vertMap[(i1, i3)] = e3
        return [
            e1, e2, e3,
            i1, e1, e3,
            e1, i2, e2,
            e3, e2, i3
        ]

    def triArea(self, p1, p2, p3):
        v1 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v2 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        cross = self.vecCross(v1, v2)
        mag = math.sqrt(cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2])
        return mag / 2

    def vecCross(self, a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]
        )

    def transformPoint(self, point, transform):
        x = point[0]
        y = point[1]
        z = point[2]
        xx = transform.XPlane.X
        xy = transform.XPlane.Y
        xz = transform.XPlane.Z
        yx = transform.YPlane.X
        yy = transform.YPlane.Y
        yz = transform.YPlane.Z
        zx = transform.ZPlane.X
        zy = transform.ZPlane.Y
        zz = transform.ZPlane.Z
        wx = transform.WPlane.X
        wy = transform.WPlane.Y
        wz = transform.WPlane.Z
        return (xx * x + yx * y + zx * z + wx, xy * x + yy * y + zy * z + wy, xz * x + yz * y + zz * z + wz)

    def rotatePoint(self, point, pitch, yaw, roll):
        if point[0] == 0 and point[1] == 0 and point[2] == 0:
            return point
        if pitch == 0 and yaw == 0 and roll == 0:
            return point
        pitch = (math.pi / 32768) * -pitch
        yaw = (math.pi / 32768) * yaw
        roll = (math.pi / 32768) * -roll
        cosa = math.cos(yaw)
        sina = math.sin(yaw)
        cosb = math.cos(pitch)
        sinb = math.sin(pitch)
        cosc = math.cos(roll)
        sinc = math.sin(roll)
        Axx = cosa * cosb;
        Axy = cosa * sinb * sinc - sina * cosc;
        Axz = cosa * sinb * cosc + sina * sinc;
        Ayx = sina * cosb;
        Ayy = sina * sinb * sinc + cosa * cosc;
        Ayz = sina * sinb * cosc - cosa * sinc;
        Azx = -sinb;
        Azy = cosb * sinc;
        Azz = cosb * cosc;
        px = point[0]
        py = point[1]
        pz = point[2]
        return (Axx * px + Axy * py + Axz * pz, Ayx * px + Ayy * py + Ayz * pz, Azx * px + Azy * py + Azz * pz)

    def iterLen(self, array):
        n = 0
        if array is not None:
            for _ in array:
                n += 1
        return n

    def warnIfComplicated(self, volume):
        if volume.Rotation.Pitch != 0 or volume.Rotation.Yaw != 0 or volume.Rotation.Roll != 0:
            self.log(f"volume has Rotation = ({volume.Rotation.Pitch}, {volume.Rotation.Yaw}, {volume.Rotation.Roll})")
        if volume.DrawScale3D.X != 1 or volume.DrawScale3D.Y != 1 or volume.DrawScale3D.Z != 1:
            self.log(f"volume has DrawScale3D = ({volume.DrawScale3D.X}, {volume.DrawScale3D.Y}, {volume.DrawScale3D.Z})")
        agg = volume.CollisionComponent.BrushAggGeom
        length = self.iterLen(agg.SphereElems)
        if length > 0:
            self.log(f"volume has SphereElems = {length}")
        length = self.iterLen(agg.BoxElems)
        if length > 0:
            self.log(f"volume has BoxElems = {length}")
        length = self.iterLen(agg.SphylElems)
        if length > 0:
            self.log(f"volume has SphylElems = {length}")
        length = self.iterLen(agg.ConvexElems)
        if length > 1:
            self.log(f"volume has ConvexElems = {length}")

    showKill = False
    showCollision = False
    hideFake = False
    hiddenComponents = []

    def toggleKill(self):
        self.showKill = not self.showKill
        if self.showKill:
            self.colorSlot = 0
            self.updateVolumes(["PlayerKillVolume", "SeqEvent_Touch", "BehaviorVolume", "WillowBoundaryTurret"], self.killData)
            self.startDrawingVolumes(["PlayerKillVolume", "SeqEvent_Touch", "BehaviorVolume", "WillowBoundaryTurret"],
                ["Kill volumes", "Trigger volumes", "Behavior volumes", "Turrets"], self.killData)
        else:
            self.stopDrawingVolumes()
            self.showCollision = False

    def toggleCollision(self):
        self.showCollision = not self.showCollision
        if self.showCollision:
            self.colorSlot = 1
            self.updateVolumes(["BlockingMeshCollectionActor", "BlockingMeshActor", "BlockingVolume"], self.collisionData)
            self.startDrawingVolumes(["BlockingMeshCollectionActor", "BlockingMeshActor", "BlockingVolume"],
                ["Collection blocking meshes", "Blocking mesh actors", "Blocking volumes"], self.collisionData)
        else:
            self.stopDrawingVolumes()
            self.showKill = False

    def toggleFake(self):
        self.hideFake = not self.hideFake
        if self.hideFake:
            for component in FindAll("StaticMeshComponent"):
                if self.isComponentRelevant(component) and self.isComponentFake(component) and not component.HiddenGame:
                    self.hiddenComponents.append(component)
                    component.SetHidden(True)
            for terrain in FindAll("Terrain"):
                if not terrain.bBlockUnreal:
                    for tcomp in terrain.TerrainComponents:
                        if not tcomp.HiddenGame:
                            self.hiddenComponents.append(tcomp)
                            tcomp.SetHidden(True)
        else:
            for component in self.hiddenComponents:
                component.SetHidden(False)
            self.hiddenComponents = []
        self.showMessage("Hiding fake meshes" if self.hideFake else "Showing fake meshes")

    def isComponentRelevant(self, component):
        parentName = component.Outer.GetFullName()
        return ("PersistentLevel" in parentName
            and ("StaticMeshActor" in parentName or "StaticMeshCollectionActor" in parentName or "InterpActor" in parentName)
            and component.StaticMesh is not None and not "Skybox.Meshes.Sky_Dome" in component.StaticMesh.GetFullName())

    def isComponentFake(self, component):
        return (not component.CollideActors or not component.BlockActors or not component.BlockNonZeroExtent
            or component.Outer.bBlockActors == False or component.Outer.bCollideActors == False
            #or (component.StaticMesh.BodySetup is None and self.hasNoMaterials(component))
        )

    def hasNoMaterials(self, component):
        if component.Materials is not None:
            for material in component.Materials:
                if material is not None:
                    return False
        return True

    def GameInputPressed(self, input):
        # todo: flags/wires/animated effect planes/etc. are not being hidden
        # todo: investigate misleading static mesh collision (e.g. SnowDriftSingle in Windshear Waste, top of Flynt's ship)
        # py p = unrealsdk.GetEngine().GamePlayers[0].Actor.Pawn
        # py p.Location = (v.Location.X, v.Location.Y, v.Location.Z)
        # py p.Location = (v._LocalToWorld.WPlane.X, v._LocalToWorld.WPlane.Y, v._LocalToWorld.WPlane.Z)
        if input.Name == "Toggle Kill Volumes":
            self.toggleKill()
        elif input.Name == "Toggle Collision Volumes":
            self.toggleCollision()
        elif input.Name == "Toggle Fake Meshes":
            self.toggleFake()

    #@ModMenu.Hook("WillowGame.WillowDamagePipeline.KillPlayer")
    #def PipelineKill(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("WillowGame.WillowDamagePipeline.KillPlayer", caller, params)
    #    return True

    #@ModMenu.Hook("WillowGame.WillowPawn.CausePlayerDeath")
    #def PawnCause(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("WillowGame.WillowPawn.CausePlayerDeath", caller, params)
    #    return True

    #@ModMenu.Hook("WillowGame.WillowPlayerPawn.Behavior_Killed")
    #def PlayerKilled(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("WillowGame.WillowPlayerPawn.Behavior_Killed", caller, params)
    #    return True

    #@ModMenu.Hook("WillowGame.WillowPlayerController.CausePlayerDeath")
    #def ControllerCause(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("WillowGame.WillowPlayerController.CausePlayerDeath", caller, params)
    #    return True

    #@ModMenu.Hook("WillowGame.WillowPlayerController.OnCausePlayerDeath")
    #def ControllerSeq(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("WillowGame.WillowPlayerController.OnCausePlayerDeath", caller, params)
    #    return True

    #@ModMenu.Hook("Engine.SequenceOp.Activated")
    #def SeqActivate(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("Engine.SequenceOp.Activated", caller, params)
    #    return True

    #@ModMenu.Hook("Engine.SequenceOp.Deactivated")
    #def SeqDeactivate(self, caller: UObject, function: UFunction, params: FStruct) -> bool:
    #    self.LogHook("Engine.SequenceOp.Deactivated", caller, params)
    #    return True

    def LogHook(self, name, caller, params):
        self.log(f"\n{name}\ncaller: {caller}\nparams: {params}\n\n")

    SaveEnabledState = ModMenu.EnabledSaveType.LoadOnMainMenu

    def Enable(self):
        def VolumeResetHook(caller: UObject, function: UFunction, params: FStruct) -> bool:
            _ = (caller, function, params)
            self.resetAll()
            return True
        super().Enable()
        RunHook("WillowGame.WillowPlayerController.WillowClientDisableLoadingMovie", "LoadHook", VolumeResetHook)
        self.resetAll()
    
    def Disable(self):
        RemoveHook("WillowGame.WillowPlayerController.WillowClientDisableLoadingMovie", "LoadHook")
        self.resetAll()
        super().Disable()

instance = CollisionVisualizer()

if __name__ == "__main__":
    for mod in ModMenu.Mods:
        if mod.Name == instance.Name:
            if mod.IsEnabled:
                mod.Disable()
            ModMenu.Mods.remove(mod)
            instance.__class__.__module__ = mod.__class__.__module__
            break

ModMenu.RegisterMod(instance)
