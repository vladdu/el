(wire ladder
  (node (gnd 0.0) (input 1.0) output)
  (resistor (r1 1) (r2 2) (r3 1) (r4 2) (r5 1) (r6 1))
  (connect
      (gnd (#2 r2) (#2 r4) (#2 r6))
      (input (#1 r1))
      ((#2 r1) (#1 r2) (#1 r3))          ;NODE1
      ((#2 r3) (#1 r4) (#1 r5))          ;NODE2
      (output (#2 r5) (#1 r6))))

DONE

(analyze 'ladder)

DONE
