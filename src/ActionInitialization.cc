#include "ActionInitialization.hh"
#include "PrimaryGeneratorAction.hh"
#include "RunAction.hh"
#include "EventAction.hh"

	void ActionInitialization::BuildForMaster() const
	{
		SetUserAction(new RunAction);
	}
	
	void ActionInitialization::Build() const
	{
		SetUserAction(new PrimaryGeneratorAction);
		SetUserAction(new RunAction);
		SetUserAction(new EventAction);
	}

	


