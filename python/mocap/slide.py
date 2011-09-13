#_____________________________________________________________________________________________
#********************************************************************************************
#
#  Robot motion (HRP2 14 small) using:
#  - ONLY OPERATIONAL TASKS
#  - Joint limits (position and velocity)
#_____________________________________________________________________________________________
#*********************************************************************************************

import sys
from optparse import OptionParser
from dynamic_graph import plug
from dynamic_graph.sot.core import *
from dynamic_graph.sot.core.math_small_entities import Derivator_of_Matrix
from dynamic_graph.sot.dynamics import *
from dynamic_graph.sot.dyninv import *
import dynamic_graph.script_shortcuts
from dynamic_graph.script_shortcuts import optionalparentheses
from dynamic_graph.matlab import matlab
sys.path.append('..')
from dynamic_graph.sot.core.meta_task_6d import toFlags
from meta_tasks_dyn import *
from meta_task_dyn_6d import MetaTaskDyn6d
from attime import attime
from numpy import *
from robotSpecific import pkgDataRootDir,modelName,robotDimension,initialConfig,gearRatio,inertiaRotor
from matrix_util import matrixToTuple, vectorToTuple
from history import History
from zmp_estimator import ZmpEstimator
from viewer_helper import addRobotViewer,VisualPinger

#-----------------------------------------------------------------------------
# --- ROBOT SIMU -------------------------------------------------------------
#-----------------------------------------------------------------------------

robotName = 'hrp14small'
robotDim  = robotDimension[robotName]
RobotClass = RobotDynSimu
robot      = RobotClass("robot")
robot.resize(robotDim)
addRobotViewer(robot,small=True,verbose=False)
dt = 5e-3

# Similar initial position with hand forward
robot.set((-0.033328803958899381, -0.0019839923040723341, 0.62176527349722499, 2.379901541270165e-05, 0.037719492175904465, 0.00043085147714449579, -0.00028574496353126724, 0.0038294370786961648, -0.64798319906979551, 1.0552418879542016, -0.44497846451873851, -0.0038397195926379991, -0.00028578259876671871, 0.0038284398205732629, -0.64712828871069394, 1.0534202525984278, -0.4440117393779604, -0.0038387216246160054, 0.00014352031102944824, 0.013151503268540811, -0.00057411504064861592, -0.050871000025766742, 0.21782780288481224, -0.37965640592672439, -0.14072647716213352, -1.1942332339530364, 0.0055454863752273523, -0.66956710808008013, 0.1747981826611808, 0.21400703176352612, 0.38370527720078107, 0.14620204468509851, -1.1873407322935838, -0.0038746980026940735, -0.66430172366423146, 0.17500428384087438))


#-------------------------------------------------------------------------------
#----- MAIN LOOP ---------------------------------------------------------------
#-------------------------------------------------------------------------------

class EllipseTemporal:
    def __init__(self,tempo):
        self.t0 = None
        self.tempo = tempo
        self.started=False
    def set(self,center,radius,T):
        self.center=center
        self.radius=radius
        self.T = T
    def point(self):
        t=self.tempo.time
        if self.t0 == None: self.t0 = t
        w= 2*pi*(t-self.t0)/self.T
        return (self.center[0]+self.radius[0]*cos(w), self.center[1]+self.radius[1]*sin(w))
    def refresh(self):
        if self.started:
            M = array(self.sig.value)
            M[0:2,3] = self.point()
            self.sig.value = matrixToTuple(M)
    def start(self,sig):
        self.started=True
        self.sig = sig
    def stop(self): self.started = False 

traj = EllipseTemporal(robot.state)

def inc():
    robot.increment(dt)
    # Execute a function at time t, if specified with t.add(...)
    if 'refresh' in ZmpEstimator.__dict__: zmp.refresh()
    attime.run(robot.control.time)
    robot.viewer.updateElementConfig('zmp',[zmp.zmp.value[0],zmp.zmp.value[1],0,0,0,0])
    if dyn.com.time >0:
        robot.viewer.updateElementConfig('com',[dyn.com.value[0],dyn.com.value[1],0,0,0,0])
    history.record()
    traj.refresh()

from ThreadInterruptibleLoop import *
@loopInThread
def loop():
#    try:
        inc()
#    except:
#        print robot.state.time,': -- Robot has stopped --'
runner=loop()

@optionalparentheses
def go(): runner.play()
@optionalparentheses
def stop(): runner.pause()
@optionalparentheses
def next(): inc()

# --- shortcuts -------------------------------------------------
@optionalparentheses
def q():
    print robot.state.__repr__()
@optionalparentheses
def qdot(): print robot.control.__repr__()
@optionalparentheses
def iter():         print 'iter = ',robot.state.time
@optionalparentheses
def status():       print runner.isPlay

@optionalparentheses
def dump():
    history.dumpToOpenHRP('openhrp/slide')

attime.addPing( VisualPinger(robot.viewer) )


#-----------------------------------------------------------------------------
#---- DYN --------------------------------------------------------------------
#-----------------------------------------------------------------------------

modelDir  = pkgDataRootDir[robotName]
xmlDir    = pkgDataRootDir[robotName]
specificitiesPath = xmlDir + '/HRP2SpecificitiesSmall.xml'
jointRankPath     = xmlDir + '/HRP2LinkJointRankSmall.xml'

dyn = Dynamic("dyn")
dyn.setFiles(modelDir, modelName[robotName],specificitiesPath,jointRankPath)
dyn.parse()

dyn.lowerJl.recompute(0)
dyn.upperJl.recompute(0)
llimit = matrix(dyn.lowerJl.value)
ulimit = matrix(dyn.upperJl.value)
dlimit = ulimit-llimit
mlimit = (ulimit+llimit)/2
llimit[6:18] = mlimit[6:12] - dlimit[6:12]*0.48
dyn.upperJl.value = vectorToTuple(ulimit)

dyn.inertiaRotor.value = inertiaRotor[robotName]
dyn.gearRatio.value    = gearRatio[robotName]

plug(robot.state,dyn.position)
plug(robot.velocity,dyn.velocity)
dyn.acceleration.value = robotDim*(0.,)

dyn.ffposition.unplug()
dyn.ffvelocity.unplug()
dyn.ffacceleration.unplug()

dyn.setProperty('ComputeBackwardDynamics','true')
dyn.setProperty('ComputeAccelerationCoM','true')

robot.control.unplug()



#-----------------------------------------------------------------------------
# --- OPERATIONAL TASKS (For HRP2-14)---------------------------------------------
#-----------------------------------------------------------------------------

# --- Op task for the waist ------------------------------
taskWaist = MetaTaskDyn6d('taskWaist',dyn,'waist','waist')
taskChest = MetaTaskDyn6d('taskChest',dyn,'chest','chest')
taskHead = MetaTaskDyn6d('taskHead',dyn,'head','gaze')
taskrh = MetaTaskDyn6d('rh',dyn,'rh','right-wrist')
tasklh = MetaTaskDyn6d('lh',dyn,'lh','left-wrist')
taskrf = MetaTaskDyn6d('rf',dyn,'rf','right-ankle')
taskrfz = MetaTaskDyn6d('rfz',dyn,'rf','right-ankle')

for task in [ taskWaist, taskChest, taskHead, taskrh, tasklh, taskrf, taskrfz ]:
    task.feature.frame('current')
    task.gain.setConstant(50)
    task.task.dt.value = dt

# --- TASK COM ------------------------------------------------------
taskCom = MetaTaskDynCom(dyn,dt)


# --- TASK POSTURE --------------------------------------------------
featurePosture    = FeatureGeneric('featurePosture')
featurePostureDes = FeatureGeneric('featurePostureDes')
plug(dyn.position,featurePosture.errorIN)
featurePosture.sdes.value = featurePostureDes.name
featurePosture.jacobianIN.value = matrixToTuple( identity(robotDim) )

taskPosture = TaskDynPD('taskPosture')
taskPosture.add('featurePosture')
plug(dyn.velocity,taskPosture.qdot)
taskPosture.dt.value = dt

taskPosture.controlGain.value = 2

def gotoq( qref,selec=None ):
    featurePostureDes.errorIN.value = vectorToTuple( qref.transpose() )
    if selec!=None: featurePosture.selec.value = toFlags( selec )

qref = zeros((robotDim,1))
qref[29] = -0.95
gotoq(qref,[29])

# --- Task lim ---------------------------------------------------
taskLim = TaskDynLimits('taskLim')
plug(dyn.position,taskLim.position)
plug(dyn.velocity,taskLim.velocity)
taskLim.dt.value = dt

dyn.upperJl.recompute(0)
dyn.lowerJl.recompute(0)
taskLim.referencePosInf.value = dyn.lowerJl.value
taskLim.referencePosSup.value = dyn.upperJl.value

#dqup = (0, 0, 0, 0, 0, 0, 200, 220, 250, 230, 290, 520, 200, 220, 250, 230, 290, 520, 250, 140, 390, 390, 240, 140, 240, 130, 270, 180, 330, 240, 140, 240, 130, 270, 180, 330)
dqup = (1000,)*robotDim
taskLim.referenceVelInf.value = tuple([-val*pi/180 for val in dqup])
taskLim.referenceVelSup.value = tuple([val*pi/180 for val in dqup])

#-----------------------------------------------------------------------------
# --- SOT Dyn OpSpaceH: SOT controller  --------------------------------------
#-----------------------------------------------------------------------------

sot = SolverDynReduced('sot')
contact = AddContactHelper(sot)
sot.setSize(robotDim-6)
#sot.damping.value = 1e-2
sot.breakFactor.value = 20

plug(dyn.inertiaReal,sot.matrixInertia)
plug(dyn.dynamicDrift,sot.dyndrift)
plug(dyn.velocity,sot.velocity)

plug(sot.solution, robot.control)

#For the integration of q = int(int(qddot)).
plug(sot.acceleration,robot.acceleration)

#-----------------------------------------------------------------------------
# ---- CONTACT: Contact definition -------------------------------------------
#-----------------------------------------------------------------------------


# Left foot contact
contactLF = MetaTaskDyn6d('contact_lleg',dyn,'lf','left-ankle')
contactLF.feature.frame('desired')
contactLF.gain.setConstant(1000)
contactLF.name = "LF"

# Right foot contact
contactRF = MetaTaskDyn6d('contact_rleg',dyn,'rf','right-ankle')
contactRF.feature.frame('desired')
contactRF.name = "RF"

contactRF.support = ((0.11,-0.08,-0.08,0.11),(-0.045,-0.045,0.07,0.07),(-0.105,-0.105,-0.105,-0.105))
contactLF.support = ((0.11,-0.08,-0.08,0.11),(-0.07,-0.07,0.045,0.045),(-0.105,-0.105,-0.105,-0.105))
contactLF.support =  ((0.03,-0.03,-0.03,0.03),(-0.015,-0.015,0.015,0.015),(-0.105,-0.105,-0.105,-0.105))

#--- ZMP ---------------------------------------------------------------------
zmp = ZmpEstimator('zmp')
zmp.declare(sot,dyn)

#-----------------------------------------------------------------------------
# --- TRACE ------------------------------------------------------------------
#-----------------------------------------------------------------------------

from dynamic_graph.tracer import *
tr = Tracer('tr')
tr.open('/tmp/','slide_','.dat')

tr.add('dyn.com','com')
tr.add(taskCom.feature.name+'.error','ecom')
tr.add('dyn.waist','waist')
tr.add('dyn.rh','rh')
tr.add('zmp.zmp','')
tr.add('dyn.position','')
tr.add('dyn.velocity','')
tr.add('robot.acceleration','robot_acceleration')
tr.add('robot.control','')
tr.add(taskCom.gain.name+'.gain','com_gain')

tr.add('dyn.lf','lf')
tr.add('dyn.rf','rf')

tr.start()
robot.after.addSignal('tr.triger')
robot.after.addSignal(contactLF.task.name+'.error')
robot.after.addSignal('dyn.rf')
robot.after.addSignal('dyn.lf')
robot.after.addSignal('dyn.com')
robot.after.addSignal('sot.forcesNormal')
robot.after.addSignal('dyn.waist')

robot.after.addSignal('taskLim.normalizedPosition')
tr.add('taskLim.normalizedPosition','qn')

history = History(dyn,1,zmp.zmp)

#-----------------------------------------------------------------------------
# --- RUN --------------------------------------------------------------------
#-----------------------------------------------------------------------------

q0 = robot.state.value

sot.clear()

contact(contactLF)
contact(contactRF)

#taskCom.feature.selec.value = "111"
taskCom.gain.setByPoint(100,10,0.005,0.8)

rfz0=0.020
rf0=matrix((0.0095,-0.095,rfz0))

#traj.set( vectorToTuple(rf0[0,0:2]),(0.35,-0.2),1200 )
traj.set( vectorToTuple(rf0[0,0:2]),(0.4,-0.42),1200 )

mrf=eye(4)
mrf[0:3,3] = (0,0,-0.105)
taskrf.opmodif = matrixToTuple(mrf)
taskrf.feature.frame('desired')
taskrf.feature.selec.value = '11'
drh=eye(4)
drh[0:2,3] = vectorToTuple(rf0[0,0:2])
taskrf.ref = matrixToTuple(drh)
taskrf.gain.setByPoint(60,5,0.01,0.8)
#taskrf.gain.setByPoint(120,10,0.03,0.8)

taskrfz.opmodif = matrixToTuple(mrf)
taskrfz.feature.frame('desired')
taskrfz.feature.selec.value = '011100'
drh=eye(4)
drh[2,3]=rfz0
taskrfz.ref = matrixToTuple(drh)
taskrfz.gain.setByPoint(100,20,0.001,0.9)
taskrfz.feature.frame('desired')

taskHead.feature.selec.value='011000'
taskHead.featureDes.position.value = matrixToTuple(eye(4))

sot.push(taskLim.name)
sot.push(taskHead.task.name)
plug(robot.state,sot.position)

# --- Events ---------------------------------------------
sigset = ( lambda s,v : s.__class__.value.__set__(s,v) )
refset = ( lambda mt,v : mt.__class__.ref.__set__(mt,v) )

attime(2
       ,(lambda : sot.push(taskCom.task.name),"Add COM")
       ,(lambda : sigset(taskCom.feature.selec, "11"),"COM XY")
       ,(lambda : refset(taskCom, ( 0.01, 0.09,  0.7 )), "Com to left foot")
       )

attime(140
       ,(lambda: sot.rmContact("RF"),"Remove RF contact" )
       ,(lambda: sot.push(taskrfz.task.name), "Add RFZ")
       ,(lambda: sot.push(taskrf.task.name), "Add RF")
       ,(lambda: gotoNd(taskrfz,rf0,"11100" ), "Up foot RF")
       )

attime(150  ,lambda : sigset(taskCom.feature.selec, "11"),"COM XY")

attime(200  ,
       lambda: gotoNd(taskrf, rf0+(0.35,0.0,0),"11")  , "RF to front"       )

attime(450  ,lambda: traj.start(taskrf.featureDes.position), "RF start traj"       )
attime(1200  ,lambda: traj.stop(), "RF stop traj"       )

attime(1200 ,lambda: gotoNd(taskrf,rf0,"111011",(80,10,0.03,0.8) )  , "RF to center"       )

attime(1500  ,lambda: gotoNd(taskrfz,(0,0,0),"11100")  , "RF to ground"       )
attime(1550  
       ,(lambda: refset(taskCom,(0.01,0,0.797))  , "COM to zero"       )
       ,(lambda: sigset(taskCom.feature.selec,"11")  , "COM XY"       )
       ,(lambda: taskCom.gain.setConstant(3)  , "lower com gain"       )
)
attime(1600  ,(lambda: contact(contactRF)  , "RF to contact"       )
       ,(lambda: sigset(taskCom.feature.selec,"111")  , "COM XYZ"       )
       ,(lambda: taskCom.gain.setByPoint(100,10,0.005,0.8)  , "upper com gain"       )
       )

attime(1800, lambda: sigset(sot.posture,q0), "Robot to initial pose")

attime(2000,stop)

inc()
go()


