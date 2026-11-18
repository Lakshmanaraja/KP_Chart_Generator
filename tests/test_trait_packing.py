from pdf.trait_pagination import card_pages

def test_same_tier_small_cards_fill_gap_and_renumber():
    t=[{"code":f"P{i}","kind":"primary","h":h} for i,h in enumerate([30,30,80,20,20],1)]
    pages=list(card_pages(t,110+2.835*2,lambda x,pt:x["h"],gap=0))
    assert [x["h"] for x in pages[0][0]]==[30,30,20,20]
    assert [x["code"] for b,_,_ in pages for x in b]==["P1","P2","P3","P4","P5"]

def test_other_tier_never_jumps_ahead():
    t=[{"code":"P1","kind":"primary","h":60},{"code":"P2","kind":"primary","h":60},{"code":"S1","kind":"secondary","h":10}]
    pages=list(card_pages(t,100+2.835*2,lambda x,pt:x["h"],gap=0))
    assert [x["code"] for x in pages[0][0]]==["P1"]
