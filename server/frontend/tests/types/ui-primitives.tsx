import { createRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SelectItem } from '@/components/ui/select';
import { SheetContent } from '@/components/ui/sheet';
import { DialogHeader } from '@/components/ui/dialog';
import { Card } from '@/components/ui/card';

export const supported = <>
  <Button ref={createRef<HTMLButtonElement>()} variant="outline" size="sm" type="submit">Save</Button>
  <Input type="number" onChange={(event) => event.currentTarget.value} />
  <SelectItem value="ready">Ready</SelectItem>
  <SheetContent side="left" aria-label="Details" />
  <DialogHeader className="heading">Details</DialogHeader>
  <Card aria-label="Summary" />
</>;

// These assertions must fail compilation if the public prop types weaken.
// @ts-expect-error Unsupported visual variant.
export const invalidVariant = <Button variant="unrecognized" />;
// @ts-expect-error Button refs point to buttons, not input elements.
export const invalidRef = <Button ref={createRef<HTMLInputElement>()} />;
// @ts-expect-error Select items require a value.
export const missingValue = <SelectItem>Missing</SelectItem>;
// @ts-expect-error Sheet placement is a fixed set of supported sides.
export const invalidSide = <SheetContent side="diagonal" />;
// @ts-expect-error Event handlers must be functions.
export const invalidHandler = <Input onChange="submit" />;
