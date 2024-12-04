from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.tools.youtube_tools import YouTubeTools
from phi.tools.apify import ApifyTools
from phi.tools.exa import ExaTools

movie_recommedation_agent = Agent(
    tools=[
        ExaTools(),
        ApifyTools(web_scraper=True) 
    ],
    model=OpenAIChat(id="gpt-4o"),
    description="You are a movie recommendation agent. You search movies by doing Exa search then scraping through a website.",
    instructions=[
        "Search exa for movies",
        "Then Scrape the website https://www.imdb.com/",
        "Give a result with rating of the movie, it's genre, description, recommended age to watch,language, similar trailers like of recommended one and upcoming movies",
        "Do not give the IMDB link to the movie"
    ],
    show_tool_calls=True,
    debug_mode=True,      
    markdown=True,         
    stream=True 
)
movie_recommedation_agent.print_response("Suggest some movies for 10 year old to watch")