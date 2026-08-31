let lockCount=0
let previousOverflow=''

export function lockBodyScroll(){
  if(lockCount===0){previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden'}
  lockCount+=1
}

export function unlockBodyScroll(){
  lockCount=Math.max(lockCount-1,0)
  if(lockCount===0)document.body.style.overflow=previousOverflow
}
