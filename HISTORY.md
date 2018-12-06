# Release History

### 0.2.0 (2018-11-28)

* **Feature**: Converted ambassador, arbiter, microengine, and scanner classes to be abstract classes. Updated sample engines to use new design patterns.

The update from 0.1.2 to 0.2.0 is a breaking change for Ambassadors, Arbiters, and Microengines.

#### polyswarmclient <= 0.1.2 used this pattern:

**Ambassadors**
```
from polyswarmclient.ambassador import Ambassador
class CustomAmbassador(Ambassador):
    # Ambassador implementation here
```

**Arbiters**
```
from polyswarmclient.arbiter import Arbiter
class CustomArbiter(Arbiter):
    # Arbiter implementation here
```

**Microengines**
```
from polyswarmclient.microengine import Microengine
class CustomMicroengine(Microengine):
    # Microengine implementation here
```

#### polyswarmclient >= 0.2.0, instead use the following pattern:

**Ambassadors**
```
from polyswarmclient.abstractambassador import AbstractAmbassador
class Ambassador(AbstractAmbassador):
    # Ambassador implementation here
```

**Arbiters**
```
from polyswarmclient.abstractarbiter import AbstractArbiter
class Arbiter(AbstractArbiter):
    # Arbiter implementation here
```

**Microengines**
```
from polyswarmclient.abstractmicroengine import AbstractMicroengine

class Microengine(AbstractMicroengine):
    # Microengine implementation here
```

This implies that custom microengines now only need to provide their python module name to the `--backend` argument
instead of `module_name:CustomMicroengine`.

Additionally, as of `polyswarmclient >= 0.2.0`:

* `AbstractArbiter.scan()` and `AbstractMicroengine.scan()` will now raise an exception if it 
has not been overridden by a sub-class and the subclass did not provide a scanner to the constructor.
* `AbstractAmbassador.next_bounty()` will now raise an exception if not overridden by sub-class.

