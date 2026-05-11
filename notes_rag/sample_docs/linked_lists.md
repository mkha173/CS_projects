# Linked Lists

A linked list is a linear data structure where each element (a "node") holds a
value and a pointer to the next node. Unlike an array, the nodes don't have to
sit in contiguous memory.

## When to use one

Linked lists shine when you need cheap inserts and deletes anywhere in the
sequence — both are O(1) once you already have a pointer to the relevant node,
because you just rewire pointers instead of shifting elements like you would in
an array. They're also a natural fit when you don't know the size up front and
don't want to deal with resizing.

The cost is random access: getting the i-th element is O(i) because you have to
walk the chain. Arrays beat linked lists handily on cache locality too, which
matters more in practice than the asymptotic analysis suggests.

## Variants

- **Singly linked**: each node points to the next one. Smallest memory overhead.
- **Doubly linked**: each node also points to the previous one. Lets you walk
  backwards and delete a node in O(1) when you only have a pointer to it.
- **Circular**: the tail's next pointer loops back to the head. Useful for
  round-robin schedulers and ring buffers.

## Common interview tricks

The fast-and-slow pointer technique (also called the tortoise and hare) shows
up constantly. Two pointers walk the list at different speeds; if they ever
meet, the list has a cycle. The same idea finds the middle of a list in one
pass: when the fast pointer reaches the end, the slow pointer is at the
middle.

Reversing a linked list iteratively is another classic. Keep three pointers
(prev, curr, next), and on each step rewire curr.next to point at prev, then
slide all three forward.
