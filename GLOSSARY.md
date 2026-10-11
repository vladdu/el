# EL

A heuristic circuit analyzer after Sussman and Stallman, MIT AI Memo 328 (1975). It solves circuits by local one-step deductions, guided by the designer's intent, and can explain every result.

## Language

### Circuits

**Wiring diagram**:
The user's declaration of a circuit: its nodes, elements, connections and hints.
_Avoid_: netlist, network

**Circuit**:
What a wiring diagram becomes once it is loaded; the thing that is analyzed.
_Avoid_: network

**Element**:
A resistor, transistor or macro-element. It has terminals.
_Avoid_: component, object, device

**Node**:
A set of terminals connected together. It has a voltage, and KCL applies to it.

**Part**:
An element or a node: anything that owns quantities and has laws.
_Avoid_: object

**Law**:
A relation among a part's quantities that fills the last unfilled one, or checks consistency when all of them are filled.
_Avoid_: rule, constraint

### Values and their origins

**Quantity**:
One named electrical or parametric value of a single part of the circuit, e.g. the current into R3's #2 terminal or NODE1's voltage. A quantity is *filled* once it has a value, either a number or an expression in formal variables.
_Avoid_: slot, cell, parameter

**Premise**:
A Given or a Default: a filled quantity with no antecedents that the circuit's analysis rests on. Premises are the only quantities that `change` may target.
_Avoid_: assumption (unqualified)

**Given**:
A premise supplied by the user, such as a resistance or a node's fixed voltage.

**Default**:
A premise supplied by a component model that encodes how designers normally use the component, e.g. a transistor's zero base current.
_Avoid_: teleological assumption, intrinsic property

**Supposition**:
A quantity filled with a fresh formal variable because the user asked for its value with `what` while it had none ("wishful thinking"). Like a premise it has no antecedents, but it is not a premise: `change` may not target it.
_Avoid_: assumption (unqualified), premise

**Justification**:
The record of how a quantity was filled: the law that filled it and its antecedents, which are the quantities that law read. The justification of a premise or a supposition has no antecedents.
_Avoid_: reason, proof step

**Operating region**:
The regime a transistor is assumed to run in, e.g. active or cut off. It is a Default quantity, and laws such as BE depend on it.

**Formal variable**:
A symbol introduced as the value of a quantity, whose own value is found later by a consistency check.
_Avoid_: abstract variable, symbolic variable, formal unknown

**Pending equation**:
An equation from a consistency check that still contains more than one unsolved formal variable. It is kept until all but one of them are solved.

### Designer intent

**Hint**:
A declaration in a wiring diagram stating the purpose of a group of parts, e.g. `(vd r1 r2)` or `(cp q107 q108)`.
_Avoid_: teleological commentary

**Macro-element**:
A composite element made from simpler parts working together for one purpose. Like a primitive element, it has its own type and laws.
_Avoid_: demon
