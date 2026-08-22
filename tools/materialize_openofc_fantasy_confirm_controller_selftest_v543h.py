from pathlib import Path
import re
R=Path(__file__).resolve().parents[1]
S=R/'OpenHoldem'/'COFCRuntimeController.cpp'
O=R/'OpenHoldem'/'COFCFantasyConfirmControllerGeneratedSelftest.cpp'

def bal(text,start):
    b=text.find('{',start); d=0; q=False; esc=False
    if b<0: raise RuntimeError('opening brace missing')
    for i in range(b,len(text)):
        c=text[i]
        if q:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': q=False
        else:
            if c=='"': q=True
            elif c=='{': d+=1
            elif c=='}':
                d-=1
                if d==0:return text[start:i+1]
    raise RuntimeError('unterminated block')

def meth(t,s):
    i=t.find(s)
    if i<0: raise RuntimeError('missing '+s)
    return bal(t,i)

def main():
    t=S.read_text(encoding='utf-8-sig')
    req=['COFCFantasyConfirmGuard::Validate','fantasy_confirm_fence_.CanDispatch','fantasy_confirm_fence_.MarkDispatched','fantasy_confirm_fence_.HasAnyDispatch','ObserveUnchangedAfterDispatch','confirm_was_fantasy','baseline=UPDATED','physical retry forbidden']
    miss=[x for x in req if x not in t]
    if miss: raise RuntimeError('H runtime missing '+repr(miss))
    send=meth(t,'bool COFCRuntimeController::SendConfirm(').replace('COFCRuntimeController::','ConfirmControllerHarness::',1)
    pat=re.compile(r'  const bool fantasy = state\.players\[state\.hero_chair\]\.fantasy;\n.*?  if \(p_casino_interface == NULL \|\| !p_casino_interface->ClickRectSafely\(rect\)\) \{',re.S)
    send,n=pat.subn('  if (!TestRegion()) { Recover("missing calibrated Confirm button region"); return false; }\n  if (!TestClick()) {',send,1)
    if n!=1: raise RuntimeError('SendConfirm UI seam failed')
    tick=meth(t,'void COFCRuntimeController::Tick(')
    i=tick.find('  if (phase_ == kConfirmSent) {')
    if i<0: raise RuntimeError('Tick ConfirmSent block missing')
    block=bal(tick,i)
    for x in ['confirm_was_fantasy','HasAnyDispatch','ObserveUnchangedAfterDispatch','baseline=UPDATED','ack=TIMEOUT']:
        if x not in block: raise RuntimeError('Tick H marker missing '+x)
    if any(x in send for x in ['p_casino_interface','ReadRegion(','CString(']): raise RuntimeError('real UI survived seam')
    src=r'''#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include "COFCFantasyConfirmGuard.h"
#include "COFCFantasyConfirmFence.h"
#include "COFCVisualObservation.h"
using namespace std;
static const bool k_always_log_errors=true; static void write_log(bool,const char*,...){}
static int g_openofc_expected_round=0; static void OpenOFCOnConfirmSent(const COFCState&){}
namespace { bool allow_click=true; int boundary=0, physical=0; bool TestRegion(){return true;} bool TestClick(){++boundary;if(!allow_click)return false;++physical;return true;}
void req(bool x,const string&m){if(!x){cerr<<"FAIL: "<<m<<endl;exit(2);}}
const int D[15]={kOFCCardJoker1,kOFCCardJoker2,0,1,2,3,4,5,6,7,8,9,10,11,12};
EOFCRow row(int i){if(i==0||i==2||i==3)return kOFCRowTop;if(i==1||i<=7)return kOFCRowMiddle;return kOFCRowBottom;}
COFCState st(bool arranged=true){COFCState s;s.Reset();s.valid=true;s.player_count=2;s.hero_chair=1;s.dealer_chair=0;s.acting_chair=1;s.round_index=-1;s.fantasy_card_count=15;s.hero_can_prepare=true;s.hero_can_confirm=true;s.decision_finalizable=true;s.action_required=true;s.players[0].occupied=true;s.players[0].source_chair=0;s.players[1].occupied=true;s.players[1].source_chair=1;s.players[1].fantasy=true;s.hero_incoming_count=15;for(int i=0;i<15;++i)s.hero_incoming[i].value=D[i];if(arranged)for(int i=0;i<13;++i){s.pending[i].active=true;s.pending[i].incoming_index=i;s.pending[i].row=row(i);}return s;}
COFCVisualObservation ob(){COFCVisualObservation o;o.Reset();o.valid=true;o.player_count=2;o.hero_chair=1;o.dealer_chair=0;o.acting_chair=1;o.round_index=-1;o.fantasy_card_count=15;o.players[0].occupied=true;o.players[0].source_chair=0;o.players[1].occupied=true;o.players[1].source_chair=1;o.players[1].fantasy=true;return o;}
COFCTurnPlan pl(){COFCTurnPlan p;p.Reset();p.valid=true;p.decision_state=st(false);p.decision_state.hero_can_confirm=false;p.decision_state.action_required=false;p.target_count=13;p.to_add_count=13;for(int i=0;i<13;++i){p.target[i].card_value=D[i];p.target[i].row=row(i);p.to_add[i]=p.target[i];}p.unused_count=2;p.unused_cards[0]=D[13];p.unused_cards[1]=D[14];return p;}
}
class ConfirmControllerHarness{public:enum Phase{kIdle,kArranging,kConfirmSent,kReacquire,kReplayProbeComplete};ConfirmControllerHarness():phase_(kIdle),reacquire_stable_cycles_(0),recovery_requires_change_(false),provisional_(false),newhand_(false){}bool SendConfirm(const COFCState&);void TickConfirmSent(const COFCState&,const COFCVisualObservation&);void Bind(){plan_=pl();}void Idle(){phase_=kIdle;}void NewHand(bool x){newhand_=x;}Phase phase()const{return phase_;}bool armed()const{return fantasy_confirm_fence_.HasAnyDispatch();}bool needchange()const{return recovery_requires_change_;}
private:static string StateFingerprint(const COFCState&s){ostringstream o;o<<s.round_index<<'|'<<s.hero_incoming_count<<'|';for(int i=0;i<s.hero_incoming_count;++i)o<<s.hero_incoming[i].value<<',';o<<'|';for(int i=0;i<kOFCMaxIncomingCards;++i)if(s.pending[i].active)o<<s.pending[i].incoming_index<<'@'<<int(s.pending[i].row)<<',';const COFCPlayerBoard&b=s.players[s.hero_chair].board;for(int i=0;i<kOFCTopCards;++i)if(b.top[i].IsKnownPhysicalCard())o<<'T'<<b.top[i].value;return o.str();}bool IsKnownNewHand(const COFCState&)const{return newhand_;}bool HandlePostConfirm(const COFCState&){return true;}void ResetForKnownNewHand(const COFCState&s){fantasy_confirm_fence_.ResetForNewHand();plan_.Reset();confirm_before_.Reset();current_fingerprint_=StateFingerprint(s);recovery_requires_change_=false;phase_=kIdle;}void Recover(const string&){recovery_fingerprint_=current_fingerprint_;recovery_requires_change_=phase_==kArranging||phase_==kConfirmSent;reacquire_stable_cycles_=0;plan_.Reset();provisional_=false;phase_=kReacquire;}
Phase phase_;COFCTurnPlan plan_;COFCState confirm_before_;COFCFantasyConfirmFence fantasy_confirm_fence_;string current_fingerprint_,recovery_fingerprint_;int reacquire_stable_cycles_;bool recovery_requires_change_,provisional_,newhand_;};
'''
    src+=send+'\nvoid ConfirmControllerHarness::TickConfirmSent(const COFCState& state,const COFCVisualObservation& observation){if(phase_!=kConfirmSent)return;\n'+block+'\n}\n'
    src+=r'''namespace{
void one(){allow_click=true;boundary=physical=0;ConfirmControllerHarness c;c.Bind();auto s=st();req(c.SendConfirm(s),"first");req(physical==1&&c.armed(),"first dispatch/fence");c.Bind();req(c.SendConfirm(s),"duplicate return");req(physical==1&&c.phase()==ConfirmControllerHarness::kReacquire,"duplicate escaped");cout<<"FANTASY_CONFIRM_CONTROLLER_ONE_SHOT=PASS\n";}
void timeout(){allow_click=true;boundary=physical=0;ConfirmControllerHarness c;c.Bind();auto s=st();auto o=ob();req(c.SendConfirm(s),"setup");for(int i=0;i<19;++i){c.TickConfirmSent(s,o);req(physical==1&&c.phase()==ConfirmControllerHarness::kConfirmSent,"early timeout/resend");}c.TickConfirmSent(s,o);req(physical==1&&c.phase()==ConfirmControllerHarness::kReacquire&&c.armed(),"timeout invariant");c.Bind();auto d=s;d.players[1].board.top[0].value=D[0];req(c.SendConfirm(d),"post-timeout suppress");req(physical==1,"post-timeout resend");cout<<"FANTASY_CONFIRM_CONTROLLER_TICK_ACK_TIMEOUT=PASS\n";}
void changed(){allow_click=true;boundary=physical=0;ConfirmControllerHarness c;c.Bind();auto s=st();auto o=ob();req(c.SendConfirm(s),"setup changed");auto d=s;d.players[1].board.top[0].value=D[0];c.TickConfirmSent(d,o);req(c.phase()==ConfirmControllerHarness::kConfirmSent&&c.armed()&&physical==1,"changed state rearmed");for(int i=0;i<19;++i){c.TickConfirmSent(d,o);req(c.phase()==ConfirmControllerHarness::kConfirmSent&&physical==1,"stable changed state timed out early/resend");}c.TickConfirmSent(d,o);req(c.phase()==ConfirmControllerHarness::kReacquire&&c.armed()&&physical==1,"stable changed state never reached bounded reacquire");cout<<"FANTASY_CONFIRM_CONTROLLER_CHANGED_STATE_STABILITY=PASS\n";}
void retry(){allow_click=false;boundary=physical=0;ConfirmControllerHarness c;c.Bind();auto s=st();req(!c.SendConfirm(s),"refusal");req(physical==0&&!c.armed()&&!c.needchange(),"refusal armed");allow_click=true;c.Idle();c.Bind();req(c.SendConfirm(s)&&physical==1&&c.armed(),"safe retry");cout<<"FANTASY_CONFIRM_CONTROLLER_PREDISPATCH_RETRY=PASS\n";}
void guard(){allow_click=true;boundary=physical=0;ConfirmControllerHarness c;c.Bind();auto s=st();s.pending[12].Reset();req(!c.SendConfirm(s)&&boundary==0&&physical==0,"12-card reached IO");ConfirmControllerHarness n;n.Bind();s=st();s.hero_can_confirm=false;req(!n.SendConfirm(s)&&boundary==0,"noauth reached IO");ConfirmControllerHarness f;f.Bind();s=st();s.decision_finalizable=false;req(!f.SendConfirm(s)&&boundary==0,"non-finalizable reached IO");cout<<"FANTASY_CONFIRM_CONTROLLER_GUARD_BEFORE_IO=PASS\n";}
void newhand(){allow_click=true;boundary=physical=0;ConfirmControllerHarness c;c.Bind();auto s=st();auto o=ob();req(c.SendConfirm(s)&&c.armed(),"newhand setup");c.NewHand(true);c.TickConfirmSent(s,o);req(!c.armed()&&c.phase()==ConfirmControllerHarness::kIdle,"newhand did not reset fence");cout<<"FANTASY_CONFIRM_CONTROLLER_NEW_HAND_RESET=PASS\n";}
}
int main(){one();timeout();changed();retry();guard();newhand();cout<<"FANTASY_CONFIRM_DYNAMIC_CONTROLLER_GATE=PASS\nFIELD_PACKAGE_AUTHORIZED=0\n";return 0;}
'''
    O.write_text(src,encoding='utf-8')
    print('generated Fantasy Confirm controller regression from production SendConfirm + Tick ConfirmSent block')
if __name__=='__main__':main()
