/* Child route cutscene requests (docs/CHILD_ROUTE_DODONGO_PLAN.md C1).
 * Starts the complete scene-local source script and source Player halt. */
#ifndef OOT_ROUTE_CUTSCENE_H
#define OOT_ROUTE_CUTSCENE_H

#define OOT_ROUTE_CS_DC_OPENING 1 /* gDcOpeningCs, Bg_Breakwall DC entrance */
#define OOT_ROUTE_DC_SCRIPT 0xf14eb231u /* core_cutscene_sources.script_id(gDcOpeningCs) */

struct PlayState;
void OotCore_RouteCutscene(struct PlayState* play, unsigned int id);

#endif
