#include <tier0/platform.h>
#undef RESTRICT
#define RESTRICT

#include <tier1/convar.h>
#include <tier1/utlstring.h>
#include <entity2/entityidentity.h>
#include <entityhandle.h>
#include <igamesystem.h>
#include <igamesystemfactory.h>

IGameSystemFactory * instanceptr();

int main() {

    instanceptr()->Shutdown();

    return 0;
}
