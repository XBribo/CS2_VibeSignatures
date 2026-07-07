#include <tier0/platform.h>
#undef RESTRICT
#define RESTRICT

// Pre-define include guards to avoid heavy transitive include chains.
#define EDICT_H
#define EIFACE_H
#define INETCHANNEL_H

class CGlobalVars;
class IRecipientFilter;
class ServerClass;
struct RenderDeviceInfo_t;
typedef uint32 SpawnGroupHandle_t;

class CPlayerUserId
{
public:
    CPlayerUserId(int index) : m_Index(static_cast<unsigned short>(index)) {}

    int Get() const { return m_Index; }

private:
    unsigned short m_Index;
};

class bf_read;
enum NetChannelBufType_t : int8 {};

// Forward declarations for types added to inetworkserializer.h in hl2sdk_cs2 update
class CPlayerBitVec;
typedef void *(*SchemaClassManipulatorFn_t)(int, void *);
typedef void *(*SchemaCollectionManipulatorFn_t)(int, void *, int, int);

#include <bitvec.h>
#include <playerslot.h>
#include <tier1/convar.h>
#include <iserver.h>

INetworkGameServer * networkgameserver();
CNetworkGameServerBase * networkgameserverbase();

int main() {

    networkgameserver()->PreWorldUpdate();
    networkgameserverbase()->SetMaxClients(64);

    return 0;
}
