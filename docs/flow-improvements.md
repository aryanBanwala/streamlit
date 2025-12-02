Female from new waitlist

    - Fix Supabase auth error
    
    - If user initially redirects to whatsapp after signing in , for whatsapp integration , wahan pe we shud change userId to that supase unique code in user_data table.

    - Integrate Wati
        - Create lib functions
            - Send template
            - Receive webhook
        - Create API functions, incase for Temporal

    - Progress bar fix

    - Remove WhatsApp number asking from onboarding

    - Garbage photo check , if user uploaded some wrong photos

    - photo liveliness check
        - but also figure out , what if user somehow uploaded wrong human/garbage photos & then they got your photo is incorrect while liveliness check 
          how can they change pthose reviously send?
        - while checking that , currently if user uploads any image , we directly upload it to supabase and save , handle this as well now.
        - also where this shud be , because we are sending your photo inference also , how you look like

    - Remove the final copies and availability taking from the analyzeUserPersona call

    - integrate lotties , after the search

    - collage image API , in background process

    - parallelize background-user-analysis

    - in last when recos are generated for the user for the first time , send WA template created that we got recos

    SEARCH CHAT:
        - lets say after 3-4 batch , allow the 1st-2nd batch users to come again

        - include image feature in searching/matchmaking

        - include weightage from recent to previous queries , to take their references in higher preference to the recent one

        - update copies ( non tech )

        - update user preferences when they click on yes/no for a user intro-confirmation card

        - after user click on YES in intro-confirm card , remove availability taking

        MALE CHANGES REQUIRED:
            - make if/else for male-female , possibly in most of the copies ( create new copies )

            - remove search agent/flow from male's search chat
            

            - male-YES click from the intro-confirmation , will do multiple things:
                - generate emails and send to slack ( for vinit manual sending ).
                    ( for both M/F )    
                    - send on WhatsApp regarding payment_link/copy/email_sent_mssg/code_of_conduct_link..... ( for both M/F )
                    - create new templates for this.
                    - after payment confirmation , create webhook that will send confirmation via whatsapp
            


    TEMPORAL CHANGES: 
        - after female yes, creation of profile card for this female for the male chat. also send nudge on WA , that check some profile for you.

    




    
