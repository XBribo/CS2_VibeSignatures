#include <tier0/platform.h>
#undef RESTRICT
#define RESTRICT

// Avoid pulling edict.h's heavier transitive include chain; eiface.h only needs
// these as pointer/reference types for the IVEngineServer2 layout test.
#define EDICT_H
#define ISERVERENTITY_H
class CGlobalVars;
class CCheckTransmitInfo;
class CSharedEdictChangeInfo;
class IServerEntity;
struct edict_t;

#include <entity2/entityidentity.h>
#include <eiface.h>

IVEngineServer2 *engineserver();

int main()
{
	engineserver()->GetSteamUniverse();

	return 0;
}
